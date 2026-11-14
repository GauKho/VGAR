# Context Budget and Token Counter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The MCP servers count tokens with UTF-8 bytes/4 only (no `VGAR_TOKENIZER_MANIFEST`), and `get_related_context` takes an optional `budget_tokens` (default 12000) clamped to a 12000 server ceiling that is reported in the result and the audit log.

**Architecture:** One shared bytes/4 counter lives in `vgar.graph.token_counter` and is re-exported by `vgar.evaluation.retrieval.scoring`. The graph service factory and the metrics module use it unconditionally. Default and ceiling are constants of the MCP tool in `graph_server.py`; the service and retriever below it stay unbounded for evaluation.

**Tech Stack:** Python 3.11–3.13, MCP Python SDK 2.2.0 (`MCPServer`), pytest.

**Spec:** `docs/superpowers/specs/2026-11-14-context-budget-and-token-counter-design.md`

## Global Constraints

- Counter: `(len(text.encode("utf-8")) + 3) // 4`, label `FALLBACK:utf8_bytes_ceil_div4` (spec D1).
- The MCP servers never read `VGAR_TOKENIZER_MANIFEST`; a host that sets it is ignored without a warning (D2).
- `budget_tokens` default 12000, ceiling 12000, effective = `min(requested, 12000)` (D3, D4).
- Over-ceiling requests are clamped, never rejected; result `diagnostics.budget` and the audit record carry requested and effective budget (D5).
- No ceiling or default in `SQLiteGraphService` or `GraphContextRetriever`; evaluation scripts unchanged; `graph_version` and `task_id` stay required.
- The user commits: tasks end by listing changed files, never with `git commit` (user rule).
- Server code follows the build-server rules already in the repo: nothing on stdout, one `logging.getLogger(__name__)` per module, docstrings with `Args:`.

## Review Focus

1. `budget_tokens=True` (a bool is an `int` in Python) must answer `INVALID_LIMIT`, not pack 1 token — test in Task 3.
2. `budget_tokens=12000` exactly is not reported as clamped — test in Task 3.
3. Non-ASCII source or arguments are counted in UTF-8 bytes, not characters — tests in Task 1.
4. A stale `VGAR_TOKENIZER_MANIFEST` pointing to a missing file must not stop `vgar-graph` — test in Task 2.
5. Existing positional callers of the tool function break when the parameter moves; MCP clients call by name, but in-repo tests must be switched to keywords — Task 3, Step 5.

---

### Task 1: Shared bytes/4 counter for evaluation and metrics

**Files:**
- Modify: `src/vgar/graph/token_counter.py` (add the counter and label at module level)
- Modify: `src/vgar/evaluation/retrieval/scoring.py:323-328` (import instead of define)
- Modify: `src/vgar/mcp/tool_metrics.py:44-71` (drop `_counter`, `lru_cache` import if unused, manifest lookup)
- Modify: `docs/mcp_server/debugging.md:35`
- Test: `tests/mcp_server/test_tv2_tool_metrics.py:32-46, 80, 82`

**Interfaces:**
- Produces: `vgar.graph.token_counter.bytes_div4_counter(text: str) -> int`, `vgar.graph.token_counter.FALLBACK_COUNTER_LABEL: str`; `vgar.evaluation.retrieval.scoring` still exports both names (same objects).
- Produces: `vgar.mcp.tool_metrics.token_count(text: str) -> tuple[int, str]` returning `(bytes_div4_counter(text), FALLBACK_COUNTER_LABEL)`.

- [ ] **Step 1: Replace `test_tokens_use_the_pinned_tokenizer_when_configured` with failing tests**

```python
def test_tokens_are_utf8_bytes_div_4(monkeypatch):
    from vgar.mcp import tool_metrics

    monkeypatch.setenv("VGAR_TOKENIZER_MANIFEST", "C:/does/not/exist.json")  # ignored (spec D2)
    assert tool_metrics.token_count("abcdefgh") == (2, "FALLBACK:utf8_bytes_ceil_div4")
    assert tool_metrics.token_count("é" * 4) == (2, "FALLBACK:utf8_bytes_ceil_div4")  # 8 bytes, 4 chars
    assert tool_metrics.token_count("") == (0, "FALLBACK:utf8_bytes_ceil_div4")


def test_evaluation_and_mcp_share_one_counter():
    from vgar.evaluation.retrieval import scoring
    from vgar.graph import token_counter

    assert scoring.bytes_div4_counter is token_counter.bytes_div4_counter
    assert scoring.FALLBACK_COUNTER_LABEL == token_counter.FALLBACK_COUNTER_LABEL == "FALLBACK:utf8_bytes_ceil_div4"
```

Change the fixture records at lines 80 and 82 from `"approx_chars_div_4"` to `"FALLBACK:utf8_bytes_ceil_div4"`.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest -q tests/mcp_server/test_tv2_tool_metrics.py`
Expected: FAIL (`approx_chars_div_4` returned; `token_counter` has no `bytes_div4_counter`)

- [ ] **Step 3: Implement**

Move `FALLBACK_COUNTER_LABEL` and `bytes_div4_counter` (body and docstring unchanged) from `scoring.py` into `token_counter.py`; in `scoring.py` replace the definitions with `from vgar.graph.token_counter import FALLBACK_COUNTER_LABEL, bytes_div4_counter  # noqa: F401 - re-exported`. In `tool_metrics.py` delete `_counter()` and make `token_count` return the shared counter and label; update the module docstring (no tokenizer manifest) and the `token_count` docstring (`Returns: the count and the label FALLBACK:utf8_bytes_ceil_div4`). In `debugging.md:35` say `token_method` is `FALLBACK:utf8_bytes_ceil_div4` (UTF-8 bytes/4, the same counter as R1).

- [ ] **Step 4: Run to verify they pass, plus evaluation tests**

Run: `python -m pytest -q tests/mcp_server/test_tv2_tool_metrics.py tests/test_token_counter.py tests/test_retrieval_rt1.py`
Expected: PASS

- [ ] **Step 5: List changed files for the user**

---

### Task 2: Graph service factory always uses the shared counter

**Files:**
- Modify: `src/vgar/graph/factory.py:56-62`
- Test: `tests/mcp_server/test_tv2_context_budget.py` (create)

**Interfaces:**
- Consumes: `bytes_div4_counter`, `FALLBACK_COUNTER_LABEL` from Task 1.
- Produces: `create_graph_service()` returns a `SQLiteGraphService` whose `count_tokens is bytes_div4_counter` and `counter_label == FALLBACK_COUNTER_LABEL`, whatever `VGAR_TOKENIZER_MANIFEST` holds.

- [ ] **Step 1: Write the failing tests**

Fixture `repo_env(tmp_path, monkeypatch)`: copy nothing; create `tmp_path/"repo"/"app.py"` with `def login():\n    return "café"\n`, set `VGAR_GRAPH_BACKEND=sqlite`, `VGAR_REPOSITORY_ROOT=<repo>`, `VGAR_GRAPH_DATABASE=<tmp_path>/graph.db`, delete `VGAR_GRAPH_VERSION`; build and ingest the graph with `PythonGraphBuilder(repo_key="demo/budget", repository_revision="fixture").build(repo)` into `SQLiteGraphStore(<db>)`; return `(repo, document)`.

```python
def test_factory_counts_bytes_without_tokenizer(repo_env, monkeypatch):
    monkeypatch.delenv("VGAR_TOKENIZER_MANIFEST", raising=False)
    service = create_graph_service()
    assert service.count_tokens is bytes_div4_counter
    assert service.counter_label == "FALLBACK:utf8_bytes_ceil_div4"
    repo, document = repo_env
    anchor = next(n["id"] for n in document["nodes"] if n["type"] == "Function")
    result = service.get_related_context([anchor], 1000, graph_version=document["graph_version"], task_id="t")
    assert result["context"]["items"] and result["counter_label"] == "FALLBACK:utf8_bytes_ceil_div4"


def test_factory_ignores_a_stale_tokenizer_variable(repo_env, monkeypatch):
    monkeypatch.setenv("VGAR_TOKENIZER_MANIFEST", str(repo_env[0] / "missing_manifest.json"))
    service = create_graph_service()
    assert service.counter_label == "FALLBACK:utf8_bytes_ceil_div4"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest -q tests/mcp_server/test_tv2_context_budget.py`
Expected: first test FAIL (`count_tokens` is `None`), second FAIL (manifest error raised)

- [ ] **Step 3: Implement**

In `factory.py` delete the manifest branch and pass `count_tokens=bytes_div4_counter, counter_label=FALLBACK_COUNTER_LABEL` to `SQLiteGraphService`. `sqlite_service.py:100` is unchanged.

- [ ] **Step 4: Run to verify they pass, plus server start-up tests**

Run: `python -m pytest -q tests/mcp_server`
Expected: PASS except failures already present before this plan (record them before Task 1)

- [ ] **Step 5: List changed files for the user**

---

### Task 3: Default and ceiling of `get_related_context`

**Files:**
- Modify: `src/vgar/mcp/servers/graph_server.py:200-212`
- Modify: `src/vgar/mcp/proposal/prompts.py:21`
- Modify: `tests/test_w5_w6_mcp.py:47,51,55,58`, `tests/test_w7_w8_m1.py:64,80` (keyword arguments)
- Modify: `docs/mcp_server/tools.md` (`get_related_context` entry)
- Test: `tests/mcp_server/test_tv2_context_budget.py`

**Interfaces:**
- Consumes: Task 2 factory (the tests set `graph_server.graph_service` directly).
- Produces: `graph_server.DEFAULT_CONTEXT_BUDGET = 12000`, `graph_server.MAX_CONTEXT_BUDGET = 12000`; tool signature `get_related_context(anchor_ids: list[str], graph_version: str, task_id: str, budget_tokens: int = DEFAULT_CONTEXT_BUDGET, issue_text: str = "", failing_tests: list[str] | None = None) -> dict[str, Any]`; successful result `data["diagnostics"]["budget"] == {"requested": int, "effective": int, "ceiling": 12000, "clamped": bool}`; audit payload keys `budget_tokens` (requested) and `effective_budget_tokens`.

- [ ] **Step 1: Write the failing tests**

Fixture `big_server(tmp_path, monkeypatch)`: repo with `app.py` holding 20 functions `f0 … f19`, each a body of about 4000 ASCII bytes (for example a docstring of `"x" * 4000`), so the whole file is above 12000 bytes/4 tokens; build and ingest as in Task 2; set `graph_server.graph_service = SQLiteGraphService(store, repository_root=repo, count_tokens=bytes_div4_counter, counter_label=FALLBACK_COUNTER_LABEL)` and `graph_server._audit_logger = AuditLogger(tmp_path/"audit.jsonl")`; return `(anchors, version, audit_path)` with `anchors` = all Function ids.

```python
def _budget(response):
    assert response["status"] == "PASS", response
    return response["data"]["diagnostics"]["budget"], response["data"]["context"]["total_token_count"]


def test_budget_defaults_to_12000(big_server):
    anchors, version, _ = big_server
    budget, total = _budget(graph_server.get_related_context(anchors, graph_version=version, task_id="t"))
    assert budget == {"requested": 12000, "effective": 12000, "ceiling": 12000, "clamped": False}
    assert 0 < total <= 12000


def test_budget_above_ceiling_is_clamped_and_audited(big_server):
    anchors, version, audit = big_server
    budget, total = _budget(graph_server.get_related_context(anchors, graph_version=version, task_id="t",
                                                             budget_tokens=50000))
    assert budget == {"requested": 50000, "effective": 12000, "ceiling": 12000, "clamped": True}
    assert total <= 12000
    record = [json.loads(l)["payload"] for l in audit.read_text(encoding="utf-8").splitlines()][-1]
    assert record["tool"] == "get_related_context"
    assert record["budget_tokens"] == 50000 and record["effective_budget_tokens"] == 12000


def test_budget_below_ceiling_is_kept(big_server):
    anchors, version, _ = big_server
    budget, total = _budget(graph_server.get_related_context(anchors, graph_version=version, task_id="t",
                                                             budget_tokens=4000))
    assert budget["effective"] == 4000 and budget["clamped"] is False and total <= 4000


def test_budget_at_ceiling_is_not_clamped(big_server):
    anchors, version, _ = big_server
    budget, _ = _budget(graph_server.get_related_context(anchors, graph_version=version, task_id="t",
                                                         budget_tokens=12000))
    assert budget["clamped"] is False


@pytest.mark.parametrize("bad", [0, -1, True])
def test_invalid_budget_is_rejected(big_server, bad):
    anchors, version, _ = big_server
    response = graph_server.get_related_context(anchors, graph_version=version, task_id="t", budget_tokens=bad)
    assert response["error"]["code"] == "INVALID_LIMIT"


async def test_schema_makes_budget_optional_with_default():
    tool = next(t for t in await graph_server.mcp.list_tools() if t.name == "get_related_context")
    schema = tool.inputSchema
    assert schema["properties"]["budget_tokens"]["default"] == 12000
    assert "budget_tokens" not in schema.get("required", [])
```

Use the async-test style already used in `tests/mcp_server` (check `pytest.ini`/`pyproject.toml` for `asyncio_mode`; if absent, wrap with `anyio.run`).

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest -q tests/mcp_server/test_tv2_context_budget.py`
Expected: FAIL (`budget_tokens` required; no `diagnostics.budget`)

- [ ] **Step 3: Implement in `graph_server.py`**

- Constants above the tool, commented `# [P] §9.2 line 972` and `# [P] §10.5 line 1134 (resource limit per tool)`.
- New signature as in Interfaces. `effective = min(budget_tokens, MAX_CONTEXT_BUDGET)` passed to `graph_service.get_related_context`; invalid values (0, negatives, bool) keep failing in `retrieval.py:179` with `INVALID_LIMIT` (`min(True, 12000)` is `True`, still a bool). On success, add `data["diagnostics"]["budget"]` with the four keys.
- `audit_fields`: `{"graph_version", "task_id", "budget_tokens": budget_tokens, "effective_budget_tokens": effective}`.
- Docstring, read by the agent: `budget_tokens` is optional, defaults to 12000 and is capped at 12000; it counts UTF-8 bytes/4, not the model's tokens; it bounds this one call; `diagnostics.budget` says whether the request was clamped. Include an `Args:` section for every parameter.

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest -q tests/mcp_server/test_tv2_context_budget.py`
Expected: PASS

- [ ] **Step 5: Switch in-repo positional callers to keywords and update prompt and docs**

`tests/test_w5_w6_mcp.py:47` becomes `graph_server.get_related_context(anchors, graph_version=version, task_id="one", budget_tokens=100, issue_text="login fails")`; apply the same to lines 51, 55, 58 and `tests/test_w7_w8_m1.py:64, 80`. `prompts.py:21`: replace "actual tokenizer accounting and limits remain enforced by the host/retrieval service" with "the server caps get_related_context at 12000 tokens (UTF-8 bytes/4)". `tools.md`: budget optional, default 12000, ceiling 12000, `diagnostics.budget` keys.

- [ ] **Step 6: Run affected suites**

Run: `python -m pytest -q tests/test_w5_w6_mcp.py tests/test_w7_w8_m1.py tests/mcp_server`
Expected: PASS except the failures recorded before Task 1 (prompt snapshot tests, if any, updated to the new sentence)

- [ ] **Step 7: List changed files for the user**

---

### Task 4: README and full suite

**Files:**
- Modify: `README.md` (environment table, "Token usage and latency", "Working session", "Tools, resources and prompt")

**Interfaces:**
- Consumes: behaviour of Tasks 1–3.

- [ ] **Step 1: Update README**

Remove the `VGAR_TOKENIZER_MANIFEST` row. "Token usage and latency": counts are UTF-8 bytes/4 (`FALLBACK:utf8_bytes_ceil_div4`, the counter of R1), measured tool-side; real model tokens come from the host; rename or delete metric files written before this change (they hold `approx_chars_div_4`) before a measured run. "Tools, resources and prompt": `get_related_context` budget is optional, default and ceiling 12000, bounds one call, clamped requests are reported in `diagnostics.budget`.

- [ ] **Step 2: Check README links and the absence of the variable**

Run: `grep -n "VGAR_TOKENIZER_MANIFEST\|approx_chars_div_4" README.md docs/mcp_server/*.md src/vgar/mcp -r`
Expected: only the README sentence about old metric files mentions `approx_chars_div_4`; no `VGAR_TOKENIZER_MANIFEST` under `src/vgar/mcp` or in `README.md`

- [ ] **Step 3: Full suite**

Run: `python -m pytest -q`
Expected: same failures as before Task 1, nothing new

- [ ] **Step 4: List all changed files and the commit command for the user**
