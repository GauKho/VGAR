# Đợt 5: thu nhỏ output của tool VGAR cho agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Output MCP của VGAR gọn lại: JSON không thụt lề cho mọi tool; `get_related_context` dùng mục gọn, mặc định 4000, giới hạn
32 KiB; `verify_patch_graph_constraints` mặc định trả bản tóm tắt; `status` ngoài cùng là kết luận của tool kiểm.

**Architecture:** Chỉ sửa tầng MCP. Module thuần mới `src/vgar/mcp/agent_output.py` chứa các hàm đổi hình dạng (JSON gọn, mục
context gọn và cắt 32 KiB, bản tóm tắt verify). `server_factory.py` gửi text gọn cho cả ba server; `tooling.run_tool` nhận hàm
`verdict`; `graph_server.py` và `execution_server.py` dùng các hàm này ở nhánh không có provider. Service, retrieval,
`ContextPayload`, R1, handoff giữ nguyên.

**Tech Stack:** Python 3.11, MCP SDK 2.2.0 (`MCPServer`), pydantic, anyio, pytest.

**Spec:** `docs/superpowers/specs/2026-11-24-tv2-smaller-tool-output-design.md` (bản nháp 1; §6.1 đã chốt với TV2 ngày 24/11).

## Global Constraints

- Không `git commit`: TV2 tự commit. Bước cuối mỗi task là liệt kê file đã đổi.
- Chạy test: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider <đường dẫn>` trong `D:\kltn\vgar_mcp_mvp_demo`.
- Luật server MCP: không in ra stdout; `logger = logging.getLogger(__name__)`; hàm public có docstring với mục `Args:`.
- Không đổi: `src/vgar/graph/*`, `src/vgar/contracts/*`, `src/vgar/repair/*`, `core_tools` và nhánh provider
  (`core_tools.respond*`), resource, prompt, R1, handoff.
- JSON gọn: `json.dumps(value, ensure_ascii=False, separators=(",", ":"))`; số byte = `len(text.encode("utf-8"))`.
- Hằng số (chép đúng): `DEFAULT_CONTEXT_BUDGET = 4000`, `MAX_CONTEXT_BUDGET = 12000`, `RESPONSE_LIMIT_BYTES = 32 * 1024`,
  `AGENT_CONTEXT_FORMAT = "vgar.context.agent.v1"`.
- Chuỗi cố định (chép đúng):
  - `diagnostics.budget_hint`: `f"the token budget ({effective}) left out lower-ranked items; budget_tokens can go up to {MAX_CONTEXT_BUDGET}"`
  - `diagnostics.response_limit = {"limit_bytes": 32768, "dropped_items": n, "over_limit": <bool>, "hint": <câu>}`; câu khi
    n > 0: `f"the response is kept under 32 KiB, so the {n} lowest-ranked items were dropped; call again with fewer anchor_ids, or read the files, if you need them"`;
    khi n == 0 (chỉ over_limit): `"the top-ranked item alone is larger than 32 KiB; it is returned whole"`
  - kết luận ERROR: `ToolError(code="INTERNAL_ERROR", message=redact_text(f"the check did not finish: {'; '.join(data.get('reasons') or [])}"))`
  - `summary` của verify: quy tắc ở Task 3, Step 3.
- Mục context: đúng thứ tự khóa `node_id, path, lines, score, distance, why, snippet`.

### Quyết định của plan (chi tiết hoá hoặc sửa spec; TV2 duyệt cùng plan)

1. `status` ngoài cùng = kết luận chỉ áp cho nhánh **không có provider** của `verify_patch_graph_constraints` và
   `run_relevant_tests` (spec §4.4 trỏ `execution_server.py:98-127`; §4.3 giữ nguyên nhánh provider). Nhánh provider của TV1
   (`tests/mcp_server/test_core_wire.py` chờ PASS ngoài cùng khi `data.status` là FAIL) không đổi.
2. `unsupported_changes` lấy từ `checks.api.details.diagnostics`, bỏ trùng hai phía baseline/candidate. Spec §4.3 ghi "giao
   của `analysis_scope.selected` với `excluded_diagnostics`" là sai: trong output thật của lỗi 5 (phiên A), `ALLOWED_TRANSITIONS`
   nằm ở `api.details.diagnostics`; `_filter_scope` (`repair/api_check.py:417-445`) chỉ để vào `excluded_diagnostics` các symbol
   **không** bị sửa.
3. Kết luận ERROR dùng mã `INTERNAL_ERROR` có sẵn, vì `docs/mcp_server/contract.md` §2.1 cấm thêm mã lỗi runtime. Thông điệp
   mang `reasons`.
4. Gợi ý khi budget cắt nằm ở khóa riêng `diagnostics.budget_hint` (không đặt trong `diagnostics.budget`, để các test so sánh
   nguyên dict `budget` vẫn đúng). `over_limit` và câu gợi ý nằm trong `diagnostics.response_limit`.
5. Kết luận không phải PASS/FAIL/NOT_RUN (ERROR hoặc giá trị lạ) → `status` ERROR.

## Review Focus

- Node id trùng tên có hậu tố `@definition:<dòng>:<cột>`: `why` phải hiện tên đầy đủ, không phải "0" (test ở Task 4).
- Budget nhỏ hơn mọi đoạn code (`items == []`, `truncated == true`): có `budget_hint`, không có `response_limit`, không lỗi (test ở Task 4).
- `verify` PASS nhưng có file không kiểm được (file mới): `summary` phải nói "not checked" (test ở Task 3).
- Chẩn đoán API có ở cả baseline và candidate: `unsupported_changes` chỉ một mục (test ở Task 3).
- Ký tự không phải ASCII (`café`): text gọn giữ nguyên ký tự, không thành `\u00e9` (test ở Task 1).

---

### Task 1: JSON gọn cho mọi tool (spec §4.1)

**Files:**
- Create: `src/vgar/mcp/agent_output.py`
- Modify: `src/vgar/mcp/server_factory.py` (cả file, 63 dòng)
- Create: `tests/mcp_server/test_tv2_compact_json.py`

**Interfaces:**
- Produces: `vgar.mcp.agent_output.compact_json(value: Any) -> str`. `create_server(...)` và `create_resource_server(...)` trả
  server mà `call_tool` gửi text gọn; `structured_content` không đổi.

- [ ] **Step 1: Viết test**

```python
COMPACT = '{"a":[1,2],"b":"café"}'

@pytest.mark.parametrize("make", [lambda: create_server("t"), lambda: create_resource_server("t", lambda uri: "")])
def test_factory_servers_send_compact_text_and_keep_structured_content(make):
    server = make()

    @server.tool()
    def sample() -> dict[str, Any]:
        return {"a": [1, 2], "b": "café"}

    async def run():
        async with Client(server, mode="2026-07-28") as client:
            return await client.call_tool("sample", {})
    result = anyio.run(run)
    assert result.content[0].text == COMPACT
    assert result.structured_content == {"a": [1, 2], "b": "café"}

@pytest.mark.parametrize("module,tool,args", [(graph_server, "get_callers", {"symbol_id": "x", "depth": 0}),
                                              (execution_server, "health", {}), (repository_server, "health", {})])
def test_every_vgar_server_sends_compact_text(module, tool, args, tmp_path, monkeypatch):
    monkeypatch.setattr(module, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    result = anyio.run(module.mcp.call_tool, tool, args)
    text = result.content[0].text
    assert "\n" not in text and text == compact_json(result.structured_content)

def test_calling_the_tool_function_still_returns_a_dict(tmp_path, monkeypatch):
    monkeypatch.setattr(execution_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    assert execution_server.health()["status"] == "PASS"
```

(`get_callers` với `depth=0` trả envelope ERROR, đủ để kiểm text của graph server mà không cần graph.)

- [ ] **Step 2: Chạy, thấy FAIL** — `ImportError: cannot import name 'compact_json'`; sau khi có hàm, test đầu fail vì text bắt đầu `'{\n  "a"'`.

- [ ] **Step 3: Cài đặt**
  - `agent_output.py`: docstring module "Shapes of VGAR tool output sent to agents (spec 2026-11-24)", logger, `compact_json`.
  - `server_factory.py`: lớp cấp module `_CompactServer(MCPServer)` ghi đè `async def call_tool(self, name, arguments, context=None)`:
    gọi `super().call_tool(...)`; khi kết quả là `CallToolResult` có `structured_content is not None`, trả
    `result.model_copy(update={"content": [TextContent(type="text", text=compact_json(result.structured_content))]})`, ngược lại
    trả nguyên. `create_server` trả `_CompactServer(...)`; `ResourceServer` kế thừa `_CompactServer`. Một dòng chú thích lý do:
    SDK 2.2 dựng text bằng `indent=2` (`func_metadata.py:653`).

- [ ] **Step 4: Chạy, thấy PASS** — file test mới, rồi `tests/mcp_server/test_core_wire.py tests/mcp_server/test_security_wire.py tests/mcp_server/test_tv2_context_budget.py`.

- [ ] **Step 5: Liệt kê file** — `src/vgar/mcp/agent_output.py`, `src/vgar/mcp/server_factory.py`, `tests/mcp_server/test_tv2_compact_json.py`.

---

### Task 2: `status` ngoài cùng là kết luận (spec §4.4)

**Files:**
- Modify: `src/vgar/mcp/tooling.py` (`run_tool` dòng 137–214)
- Modify: `src/vgar/mcp/servers/graph_server.py` (`_tool` dòng 59–85; `verify_patch_graph_constraints` dòng 594–622)
- Modify: `src/vgar/mcp/servers/execution_server.py` (`run_relevant_tests` dòng 96–132)
- Modify: `src/vgar/mcp/schemas.py` (docstring module, dòng 8–12)
- Modify: `docs/mcp_server/contract.md:28`
- Test: `tests/test_mcp_tool_contract.py`, `tests/test_patch_checks_from_snapshot.py`

**Interfaces:**
- Produces: `run_tool(..., verdict: Callable[[dict[str, Any]], str] | None = None) -> dict[str, Any]` (`run_tool_async` chuyển
  tiếp qua `**kwargs`, không đổi); `graph_server._tool(tool, call, audit_fields, summarize, verdict=None)`.

- [ ] **Step 1: Viết test**

Trong `tests/test_mcp_tool_contract.py`, sau `test_run_tool_marks_untrusted_text`:

```python
@pytest.mark.parametrize("verdict", ["PASS", "FAIL", "NOT_RUN"])
def test_run_tool_puts_the_verdict_in_the_outer_status(tmp_path, verdict):
    from vgar.mcp.tooling import run_tool
    audit = AuditLogger(tmp_path / "audit.jsonl")
    response = run_tool(server="t", tool="x", backend="b", audit=audit, call=lambda: {"status": verdict},
                        verdict=lambda data: data["status"])
    assert response["status"] == verdict and response["data"] == {"status": verdict} and response["error"] is None
    assert json.loads(audit._path.read_text(encoding="utf-8").splitlines()[-1])["payload"]["status"] == verdict

@pytest.mark.parametrize("verdict", ["ERROR", "SOMETHING_ELSE"])
def test_run_tool_check_error_keeps_data_and_sets_error(tmp_path, verdict):
    from vgar.mcp.tooling import run_tool
    response = run_tool(server="t", tool="x", backend="b", audit=AuditLogger(tmp_path / "audit.jsonl"),
                        call=lambda: {"status": verdict, "reasons": ["PATCH_REJECTED: bad hunk"]},
                        verdict=lambda data: data["status"])
    assert response["status"] == "ERROR" and response["data"]["status"] == verdict
    assert response["error"]["code"] == "INTERNAL_ERROR" and "PATCH_REJECTED: bad hunk" in response["error"]["message"]

def test_run_tool_without_a_verdict_stays_pass(tmp_path):
    from vgar.mcp.tooling import run_tool
    response = run_tool(server="t", tool="x", backend="b", audit=AuditLogger(tmp_path / "audit.jsonl"),
                        call=lambda: {"status": "FAIL"})
    assert response["status"] == "PASS"
```

Cuối `tests/test_patch_checks_from_snapshot.py` (mục `# --- Batch 5: outer status is the verdict`):

```python
def test_verify_outer_status_is_not_run_without_changes(served, tmp_path):
    response = verify()
    assert response["status"] == response["data"]["status"] == "NOT_RUN"
    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[-1])["payload"]["status"] == "NOT_RUN"

def test_verify_outer_status_is_fail_on_a_syntax_error(served):
    (served[1] / "shop/pricing.py").write_text("def round_vnd(amount):\n    return (\n", encoding="utf-8", newline="")
    assert verify()["status"] == "FAIL"

def test_verify_outer_status_is_pass_when_every_check_passes(served):
    _edit_pricing(served[1])
    assert verify()["status"] == "PASS"

def test_verify_that_cannot_finish_is_error_and_keeps_its_data(served):
    response = anyio.run(lambda: graph_server.verify_patch_graph_constraints(diff="not a diff"))
    assert response["status"] == "ERROR" and response["data"]["status"] == "ERROR"
    assert response["error"]["code"] == "INTERNAL_ERROR" and "PATCH_REJECTED" in response["error"]["message"]

def test_run_relevant_tests_outer_status_is_not_run_without_related_tests(tmp_path, monkeypatch):
    service, version, root = _build(tmp_path)
    monkeypatch.setattr(execution_server, "_graph_service", service)
    monkeypatch.setattr(execution_server, "_audit_logger", AuditLogger(tmp_path / "x.jsonl"))
    _edit_pricing(root)
    response = anyio.run(execution_server.run_relevant_tests)
    assert response["status"] == "NOT_RUN" and response["data"]["reasons"] == ["NO_RELATED_TESTS"]

def test_a_tool_without_a_verdict_stays_pass(served):
    assert graph_server.search_symbols("round_vnd")["status"] == "PASS"
```

- [ ] **Step 2: Chạy, thấy FAIL** — `TypeError: run_tool() got an unexpected keyword argument 'verdict'`; các test tool thấy `'PASS' == 'NOT_RUN'`.

- [ ] **Step 3: Cài đặt**
  - `run_tool`: gọi `verdict(data)` trong cùng khối `try` với `call()`/`summarize` (lỗi của nó thành envelope ERROR như mọi
    lỗi khác). Không có lỗi và có kết luận: `status` = kết luận nếu thuộc PASS/FAIL/NOT_RUN, ngược lại ERROR với `error` theo
    chuỗi cố định, giữ `data`. Tính `status` trước khi ghi audit (audit ghi `status` ngoài cùng). Docstring thêm `verdict`.
  - `graph_server._tool`: thêm `verdict=None`, chuyển vào `run_tool`. Nhánh không provider của verify truyền
    `verdict=lambda data: data["status"]`; `execution_server.run_relevant_tests` (nhánh không provider) cũng vậy.
  - Docstring hai tool thêm: "The outer ``status`` is the verdict: PASS, FAIL, NOT_RUN (not verified) or ERROR (the check did
    not finish; ``data`` is kept)."
  - `schemas.py` dòng 8–12 thay bằng: ERROR → `error` có giá trị; `data` null, trừ tool kiểm có kết luận ERROR (giữ `data`);
    FAIL/NOT_RUN là kết luận của `verify_patch_graph_constraints` và `run_relevant_tests` (không provider); tool khác chỉ trả
    PASS hoặc ERROR.
  - `contract.md:28`: thay câu "PASS nghĩa tool trả lời được; ví dụ repair `data.verdict=FAIL|ERROR` vẫn có envelope PASS." bằng:
    tool có kết luận (`verify_patch_graph_constraints`, `run_relevant_tests`, nhánh không provider) đặt kết luận ở `status` ngoài
    cùng (PASS/FAIL/NOT_RUN; `data.status` ERROR → `status` ERROR, giữ `data`, `error.code` `INTERNAL_ERROR`); nhánh provider và
    các tool khác giữ PASS = tool trả lời được, ERROR = không trả lời được.

- [ ] **Step 4: Chạy, thấy PASS** — hai file test trên, rồi bộ hồi quy:
  `tests/mcp_server tests/test_tv2_patch_evidence.py tests/test_agent_loop_fixes.py tests/test_graph_tools_agent_feedback.py tests/test_mcp_day5.py tests/test_mcp_legacy_servers.py`.
  Test nào chờ `status` ngoài cùng PASS trong khi `data.status` (nhánh không provider) khác PASS: sửa kỳ vọng thành kết luận,
  không sửa gì khác.

- [ ] **Step 5: Liệt kê file** — `src/vgar/mcp/tooling.py`, `src/vgar/mcp/servers/graph_server.py`,
  `src/vgar/mcp/servers/execution_server.py`, `src/vgar/mcp/schemas.py`, `docs/mcp_server/contract.md`,
  `tests/test_mcp_tool_contract.py`, `tests/test_patch_checks_from_snapshot.py`, cộng các test hồi quy đã sửa.

---

### Task 3: `verify_patch_graph_constraints` trả bản tóm tắt (spec §4.3)

**Files:**
- Modify: `src/vgar/mcp/agent_output.py`
- Modify: `src/vgar/mcp/servers/graph_server.py` (`verify_patch_graph_constraints`)
- Modify: `README.md:169`, `docs/mcp_server/contract.md` (dòng `verify_patch_graph_constraints` của bảng §3)
- Test: `tests/test_patch_checks_from_snapshot.py`

**Interfaces:**
- Consumes: `verdict` của Task 2 (verify vẫn truyền `verdict=lambda data: data["status"]`).
- Produces: `verify_view(result: dict[str, Any], details: bool) -> dict[str, Any]`; tool
  `verify_patch_graph_constraints(diff: str = "", details: bool = False)`.

- [ ] **Step 1: Viết test** (cuối `tests/test_patch_checks_from_snapshot.py`, mục `# --- Batch 5: verify summary`)

```python
ORDER = ('class Status:\n    NEW = "new"\n    PAID = "paid"\n\n\nALLOWED = {Status.NEW: [Status.PAID]}\n\n\n'
         'def can_move(a, b):\n    return b in ALLOWED.get(a, [])\n')

@pytest.fixture
def served_order(tmp_path, monkeypatch):
    """A module constant the API check cannot read (non-literal value), edited in the working tree: like ALLOWED_TRANSITIONS."""
    service, version, root = _build(tmp_path, {**SHOP, "shop/order.py": ORDER})
    _serve(tmp_path, monkeypatch, service)
    (root / "shop/order.py").write_text(ORDER.replace("[Status.PAID]", "[Status.PAID, Status.NEW]"), encoding="utf-8", newline="")
    return version, root

def test_verify_summary_names_the_unsupported_module_constant(served_order):
    response = verify()
    data = response["data"]
    assert response["status"] == "NOT_RUN"
    assert set(data) == {"status", "reasons", "graph_version", "diff_sha256", "summary", "checks",
                         "unsupported_changes", "diagnostic_counts", "checked_diff"}
    assert data["summary"] == "Change NOT verified: api NOT_RUN (API_UNSUPPORTED_DECLARATION: ALLOWED in shop/order.py)"
    assert data["unsupported_changes"] == [{"symbol": "ALLOWED", "path": "shop/order.py", "reason": "API_UNSUPPORTED_DECLARATION"}]
    assert data["diagnostic_counts"]["API_UNSUPPORTED_DECLARATION"] == 2   # baseline + candidate
    assert all(set(check) == {"status", "reasons"} for check in data["checks"].values())
    assert "diff" not in data["checked_diff"] and data["checked_diff"]["files"] == ["shop/order.py"]

def test_verify_with_details_keeps_the_full_checks(served_order):
    data = anyio.run(lambda: graph_server.verify_patch_graph_constraints(details=True))["data"]
    assert "analysis_scope" in data["checks"]["api"]["details"] and data["checked_diff"]["diff"]
    assert data["summary"].startswith("Change NOT verified: api NOT_RUN")

def test_verify_summary_of_a_passing_change_lists_unchecked_files(served):
    _edit_pricing(served[1])
    (served[1] / "scratch.py").write_text("print(1)\n", encoding="utf-8")
    assert verify()["data"]["summary"] == ("Change verified: schema, structural, api, source_imports, port_check PASS on "
                                           "shop/pricing.py; not checked: new file: scratch.py")

def test_verify_summary_without_changes_gives_the_reason(served):
    assert verify()["data"]["summary"] == "Change NOT verified: NO_CHANGES"
```

- [ ] **Step 2: Chạy, thấy FAIL** — `KeyError: 'summary'`; test `details=True` thấy `TypeError: ... unexpected keyword argument 'details'`.

- [ ] **Step 3: Cài đặt**
  - `verify_view(result, details)`: `details=True` → `{**result, "summary": ...}`. Ngược lại trả đúng các khóa của test đầu:
    `status`, `reasons`, `graph_version`, `diff_sha256` như cũ; `checks` = `{tên: {"status": ..., "reasons": list(check.get("reasons", ()))}}`;
    `unsupported_changes` = các mục `{"symbol": d.get("symbol"), "path": d["path"], "reason": d["reason"]}` của
    `checks.api.details.diagnostics` (không có check `api` → `[]`), bỏ trùng, giữ thứ tự; `diagnostic_counts` = đếm `reason`
    trên `details.diagnostics` của mọi check có `details` là dict; `checked_diff` = bản sao không có khóa `diff`.
  - `summary` (chuỗi cố định):
    - PASS: `f"Change verified: {', '.join(<tên check có status PASS, theo thứ tự checks>)} PASS on {', '.join(checked_diff['files'])}"`.
    - Khác PASS: `"Change NOT verified: " + "; ".join(parts)`. Mỗi check (theo thứ tự) có status FAIL/ERROR, hoặc NOT_RUN mà
      `reasons` không rỗng, cho một phần `f"{tên} {status}"`, thêm `f" ({', '.join(nhãn)})"` khi có nhãn; nhãn của `api` là
      `f"{reason}: {symbol} in {path}"` (không có symbol: `f"{reason} in {path}"`) từ `unsupported_changes` nếu có, các check
      khác (và `api` không có mục nào) dùng `reasons` của check. Không có phần nào → `", ".join(<reasons không bắt đầu bằng "NOT_CHECKED: ">)`.
    - Cả hai trường hợp: thêm `f"; not checked: {', '.join(checked_diff['not_checked'])}"` khi danh sách không rỗng.
  - Tool: thêm `details: bool = False`; nhánh không provider trả `verify_view(with_checked_diff(...), details)` ở cả hai
    `return`; `_verified` và cache không đổi; nhánh provider bỏ qua `details`. Docstring `Args:` thêm `details`: "False (default)
    returns a summary: ``summary``, each check's status and reasons, ``unsupported_changes``, ``diagnostic_counts``; True adds
    every check's details and the checked diff."
  - `README.md:169`: thêm một câu: `verify_patch_graph_constraints` trả bản tóm tắt (`details=true` cho chi tiết từng check);
    với nó và `run_relevant_tests`, `status` ngoài cùng là kết luận (PASS/FAIL/NOT_RUN).
  - `contract.md` §3, dòng `verify_patch_graph_constraints`: ghi tham số `details`, các khóa của bản tóm tắt và `status` ngoài cùng.

- [ ] **Step 4: Chạy, thấy PASS** — file test, rồi bộ hồi quy của Task 2. Test nào đọc `data.checks.*.details` hoặc
  `data.checked_diff.diff` qua tool: truyền `details=True`, không sửa gì khác.

- [ ] **Step 5: Liệt kê file** — `src/vgar/mcp/agent_output.py`, `src/vgar/mcp/servers/graph_server.py`, `README.md`,
  `docs/mcp_server/contract.md`, `tests/test_patch_checks_from_snapshot.py`, cộng các test hồi quy đã sửa.

---

### Task 4: `get_related_context` gọn, mặc định 4000, giới hạn 32 KiB (spec §4.2)

**Files:**
- Modify: `src/vgar/mcp/agent_output.py`
- Modify: `src/vgar/mcp/servers/graph_server.py` (dòng 223–277)
- Modify: `tests/mcp_server/test_tv2_context_budget.py`, `tests/test_w7_w8_m1.py:64-71`
- Modify: `README.md:245`, `docs/mcp_server/tools.md:13`, `docs/mcp_server/contract.md` (dòng `get_related_context` của bảng §3)

**Interfaces:**
- Consumes: `compact_json` (Task 1).
- Produces: `agent_context(data: dict[str, Any], limit_bytes: int = RESPONSE_LIMIT_BYTES) -> dict[str, Any]` (nhận output của
  service sau khi `graph_server` đã thay `diagnostics`; trả dict mới, không sửa đầu vào); `AGENT_CONTEXT_FORMAT`,
  `RESPONSE_LIMIT_BYTES`.

- [ ] **Step 1: Viết test** (`tests/mcp_server/test_tv2_context_budget.py`)

Tách thân fixture `big_server` thành `_serve_repo(tmp_path, monkeypatch, source: str) -> tuple[list[str], str, Path]` (ghi
`source` vào `app.py`, trả anchors là id các Function, graph_version, đường dẫn audit); `big_server` gọi nó với nội dung cũ.
Đổi `test_budget_defaults_to_12000` thành:

```python
def test_budget_defaults_to_4000(big_server):
    anchors, version, _ = big_server
    budget, total = _budget(graph_server.get_related_context(anchors, graph_version=version, task_id="t"))
    assert budget == {"requested": 4000, "effective": 4000, "ceiling": 12000, "clamped": False}
    assert 0 < total <= 4000
```

`test_schema_makes_budget_optional_with_default` chờ `default == 4000`. Thêm:

```python
def _size(value) -> int:
    return len(compact_json(value).encode("utf-8"))

def test_items_have_the_agent_fields(big_server):
    anchors, version, _ = big_server
    data = graph_server.get_related_context(anchors, graph_version=version, task_id="t")["data"]
    assert data["context_format"] == "vgar.context.agent.v1" and "source_metadata" not in data
    for item in data["context"]["items"]:
        assert list(item) == ["node_id", "path", "lines", "score", "distance", "why", "snippet"]
        assert item["lines"][0] <= item["lines"][1] and item["score"] == round(item["score"], 3)

def test_why_names_relations_by_qualified_name(tmp_path, monkeypatch):
    anchors, version, _ = _serve_repo(tmp_path, monkeypatch, "def a():\n    return b()\n\n\ndef b():\n    return 1\n")
    a = next(n for n in anchors if n.endswith(":app.a"))
    items = graph_server.get_related_context([a], graph_version=version, task_id="t")["data"]["context"]["items"]
    assert next(i["why"] for i in items if i["node_id"].endswith(":app.b")) == ["TASK_ANCHOR", "CALLS app.a -> app.b"]

def test_response_is_capped_at_32_kib_by_dropping_the_lowest_ranked_items(big_server):
    anchors, version, audit = big_server
    data = graph_server.get_related_context(anchors, graph_version=version, task_id="t", budget_tokens=12000)["data"]
    full = graph_server.graph_service.get_related_context(anchors, 12000, graph_version=version, task_id="t")["context"]["items"]
    kept, limit = data["context"]["items"], data["diagnostics"]["response_limit"]
    assert _size(data) <= 32768
    assert [i["node_id"] for i in kept] == [i["node_id"] for i in full[:len(kept)]]
    assert limit["limit_bytes"] == 32768 and limit["dropped_items"] == len(full) - len(kept) > 0 and limit["over_limit"] is False
    assert data["context"]["truncated"] is True
    assert data["context"]["total_token_count"] == sum(i["token_count"] for i in full[:len(kept)])
    payload = [json.loads(line)["payload"] for line in audit.read_text(encoding="utf-8").splitlines()][-1]
    assert payload["response_bytes"] == _size(data) and payload["dropped_items"] == limit["dropped_items"]

def test_budget_truncation_adds_a_hint(big_server):
    anchors, version, _ = big_server
    diagnostics = graph_server.get_related_context(anchors, graph_version=version, task_id="t")["data"]["diagnostics"]
    assert "budget_tokens can go up to 12000" in diagnostics["budget_hint"] and "response_limit" not in diagnostics

def test_a_budget_smaller_than_any_snippet_returns_no_items_and_a_hint(big_server):
    anchors, version, _ = big_server
    data = graph_server.get_related_context(anchors, graph_version=version, task_id="t", budget_tokens=1)["data"]
    assert data["context"]["items"] == [] and data["context"]["truncated"] is True
    assert "budget_hint" in data["diagnostics"] and "response_limit" not in data["diagnostics"]

def test_one_item_larger_than_the_limit_is_returned_whole(tmp_path, monkeypatch):
    anchors, version, _ = _serve_repo(tmp_path, monkeypatch, f'def huge():\n    """{"x" * 40000}"""\n')
    data = graph_server.get_related_context(anchors, graph_version=version, task_id="t", budget_tokens=12000)["data"]
    assert len(data["context"]["items"]) == 1
    assert data["diagnostics"]["response_limit"]["over_limit"] is True
    assert data["diagnostics"]["response_limit"]["dropped_items"] == 0

def test_why_shows_the_qualified_name_of_a_renamed_duplicate():
    duplicate = "vgar:r:python:function:a.py:a.f@definition:3:0"
    item = {"node_id": duplicate, "path": "a.py", "symbol": "a.f", "snippet": "def f(): ...",
            "range": {"start_line": 3, "start_col": 0, "end_line": 4, "end_col": 9}, "relevance_score": 0.12345,
            "graph_distance": 1, "confidence": 1.0, "token_count": 3,
            "graph_rationale": ["TASK_ANCHOR", f"CALLS:vgar:r:python:function:b.py:b.g->{duplicate}"]}
    data = {"context_format": "vgar.context.v1", "source_metadata": {}, "diagnostics": {},
            "context": {"anchor_ids": [], "items": [item], "total_token_count": 3, "token_budget": 4000, "truncated": False}}
    assert agent_context(data)["context"]["items"][0] == {
        "node_id": duplicate, "path": "a.py", "lines": [3, 4], "score": 0.123, "distance": 1,
        "why": ["TASK_ANCHOR", "CALLS b.g -> a.f"], "snippet": "def f(): ..."}
```

`tests/test_w7_w8_m1.py:64-71`: response của tool chờ `context_format == "vgar.context.agent.v1"`, không có `source_metadata`,
có mục `path == "app.py"`. Phần `ContextPayload.model_validate`, `schema_version`, `source_metadata[...]["content_hash"]`,
`render_context_for_repair` chuyển sang `exported = service.get_related_context([target], 1000, graph_version=version,
task_id='task', issue_text='target fails')`. Phần còn lại của test giữ nguyên.

- [ ] **Step 2: Chạy, thấy FAIL** — `test_budget_defaults_to_4000`: `requested 12000 != 4000`; test mục: thiếu `lines`; `ImportError` cho `agent_context`.

- [ ] **Step 3: Cài đặt**
  - `agent_context`: đổi từng mục theo bảng spec §4.2 (`lines = [start_line, end_line]`, `score = round(relevance_score, 3)`,
    `distance = graph_distance`, `why` = từng dòng `graph_rationale`: dòng dạng `<RELATION>:<id>-><id>` thành
    `f"{RELATION} {tên(id)} -> {tên(id)}"`, dòng khác giữ nguyên; `tên(id)` = `id.split("@definition:", 1)[0].rsplit(":", 1)[-1]`).
    Output = `data` bỏ `source_metadata`, `context_format = AGENT_CONTEXT_FORMAT`, `context.items` là các mục mới.
    Giới hạn: nếu JSON gọn của output > `limit_bytes`, bỏ dần mục cuối (giữ ít nhất một) cho đến khi vừa, đo **cả**
    `diagnostics.response_limit`. Có bỏ mục: `truncated = True`, `total_token_count` = tổng `token_count` (của service) các mục
    còn lại. Ghi `response_limit` (chuỗi cố định) khi có bỏ mục hoặc mục duy nhất còn lại vẫn vượt (`over_limit`).
  - `graph_server`: `DEFAULT_CONTEXT_BUDGET = 4000` với chú thích "deviates from [P] §9.2 (budget_tokens=12000): host output
    limits and the batch-5 measurements (spec 2026-11-24 §4.2)"; chú thích của `MAX_CONTEXT_BUDGET` giữ. Trong `call()`, sau
    khối `hint` hiện có: nếu `data["context"]["truncated"]` thì thêm `diagnostics.budget_hint`; rồi `return agent_context(data)`.
    `summarize` thêm `response_bytes` (byte JSON gọn của `data`) và `dropped_items` khi có `response_limit`.
  - Docstring `get_related_context`: budget là mức tối đa cho phần code của một lần gọi, mặc định 4000, trần 12000; phần không
    dùng không tốn gì; budget cao chỉ trả thêm code khi có; response giữ dưới 32 KiB bằng cách bỏ mục điểm thấp nhất
    (`diagnostics.response_limit`); mỗi mục gồm `node_id`, `path`, `lines`, `score`, `distance`, `why`, `snippet`.
  - `README.md:245`, `docs/mcp_server/tools.md:13`, `contract.md` §3 dòng `get_related_context`: mặc định 4000, trần 12000,
    lệch proposal §9.2 (lý do: giới hạn output của host, số đo phiên A), giới hạn 32 KiB, hình dạng mục, `vgar.context.agent.v1`;
    service vẫn trả `vgar.context.v1` cho R1 và handoff.

- [ ] **Step 4: Chạy, thấy PASS** — `tests/mcp_server/test_tv2_context_budget.py tests/test_w7_w8_m1.py tests/test_w5_w6_mcp.py tests/test_graph_tools_proposal_alignment.py tests/test_graph_tools_agent_feedback.py tests/test_agent_loop_fixes.py tests/test_m1_handoff.py`.

- [ ] **Step 5: Liệt kê file** — `src/vgar/mcp/agent_output.py`, `src/vgar/mcp/servers/graph_server.py`,
  `tests/mcp_server/test_tv2_context_budget.py`, `tests/test_w7_w8_m1.py`, `README.md`, `docs/mcp_server/tools.md`,
  `docs/mcp_server/contract.md`.

---

### Task 5: Chạy lại trên ShopFlow và toàn bộ suite (spec §5.2, §5.3)

**Files:**
- Create: `scripts/mcp_server/replay_shopflow_session.py`
- Create (kết quả chạy): `docs/status/tv2_batch5_shopflow_replay_2026-11-24.md`

**Interfaces:**
- Consumes: tool MCP của Task 1–4 qua `graph_server.mcp.call_tool`.
- Produces: CLI `replay_shopflow_session.py --source DIR --session FILE [--out FILE]`; exit 0 khi đạt cả ba tiêu chí, 1 khi không.

- [ ] **Step 1: Viết script** (docstring module ghi spec §5.2 và cách chạy)
  1. Chép `--source` (gốc repo ShopFlow ở `ee54b36`, thư mục chứa package `shopflow/`; bỏ `.git`, `__pycache__`, `.venv`) vào
     `<tmp>/shopflow`: `repo_key` là tên thư mục, và node id trong log bắt đầu bằng `vgar:shopflow:`.
  2. Đặt env **trước khi** import `graph_server`: `VGAR_GRAPH_BACKEND=sqlite`, `VGAR_REPOSITORY_ROOT=<tmp>/shopflow`,
     `VGAR_GRAPH_DATABASE=<tmp>/graph.db`, `VGAR_MCP_AUDIT_LOG=<tmp>/audit.jsonl`; bỏ `VGAR_GRAPH_VERSION`.
  3. Đọc log phiên (định dạng như `C:\Users\nlhnh\.claude\jobs\8cbd1456\tmp\simulate_final.py`: `messages[].content[]` có
     `type == "tool"`, `name == "vgar-graph_<tool>"`, `state.input`, text trong `state.content[]`; câu "full output saved to
     <file>" trỏ tới output đầy đủ). Lấy theo thứ tự input của `find_task_anchors` và `get_related_context`; diff lỗi 5 =
     `data.checked_diff.diff` của output `verify_patch_graph_constraints` đầu tiên có `API_UNSUPPORTED_DECLARATION` trong
     `data.reasons` và chứa `ALLOWED_TRANSITIONS`.
  4. Dựng graph bằng `call_tool("build_or_update_graph", {"repo_path": ...})`; in graph_version dựng lại cạnh graph_version
     trong log (bằng nhau nghĩa là cùng code).
  5. Gọi lại các lần đã ghi, theo thứ tự, thay `graph_version` bằng bản vừa dựng; đánh số các lần `get_related_context` 1..13.
     Mỗi lần ghi: số thứ tự, `status`, byte JSON gọn của `data`, byte text, số mục, `dropped_items`, hàm lỗi có/thiếu.
     Hàm lỗi chờ đợi (`node_id` kết thúc bằng `"." + tên`):
     `{9: ("Order.__init__",), 10: ("coupon_rate", "OrderService.place_order"), 11: ("quote_order",), 12: ("Notifier.order_shipped", "InventoryService.commit"), 13: ("Order.can_transition",)}`.
  6. `call_tool("verify_patch_graph_constraints", {"diff": <diff lỗi 5>})`: ghi `status`, `summary`, `unsupported_changes`.
  7. Đạt khi: mọi lần `get_related_context` có `status` PASS đều có `data` ≤ 32.768 byte; mọi hàm lỗi chờ đợi có mặt; verify
     có `status` NOT_RUN và `ALLOWED_TRANSITIONS` trong `unsupported_changes`. In bảng markdown và kết luận ra stdout (script
     gọi server trong cùng process, không qua stdio), ghi thêm vào `--out` nếu có.

- [ ] **Step 2: Chạy script** —
  `.venv/Scripts/python.exe scripts/mcp_server/replay_shopflow_session.py --source <ShopFlow ở ee54b36> --session D:\kltn\vgar-work\opencode-logs\ses_df7276b72ffetYKJMAPODVXxnI.json --out docs/status/tv2_batch5_shopflow_replay_2026-11-24.md`.
  Không có sẵn repo ShopFlow ở `ee54b36`: hỏi TV2 đường dẫn (không tự giải nén hay đoán). Kỳ vọng exit 0; số byte gần cột
  "Sau khi làm gọn" của bảng spec §4.2 (budget giờ vẫn là budget agent đã xin trong log).

- [ ] **Step 3: Chạy toàn bộ suite** — `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`. Kỳ vọng: pass hết trừ các
  lỗi Docker/harness đã biết (khoảng 3592 test cũ + test mới). Test fail khác: dừng, báo TV2 kèm output, không sửa test ngoài
  danh sách của Task 1–4.

- [ ] **Step 4: Liệt kê file** — `scripts/mcp_server/replay_shopflow_session.py`, `docs/status/tv2_batch5_shopflow_replay_2026-11-24.md`.
