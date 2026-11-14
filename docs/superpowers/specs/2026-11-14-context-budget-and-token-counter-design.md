# Context budget and token counter of the MCP servers (TV2, 14/11/2026)

## Sources

- **[P]** proposal `D:\kltn\proposal_vgar_mcp_final_corrected.md`
- **[plan]** `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (R1 belongs to it)

Decisions of the 16-week plans (M1 tokenizer acceptance 03/10, W5-6 fallback decision) are not sources for this change.

## What the proposal says about the budget

| [P] line | Section | Text |
|---|---|---|
| 27 | §1 | the core problem is "không chỉ là 'thiếu token context'" |
| 788 | §8.1 | `C_graph = retrieve(T, G, budget=B)` |
| 813, 815 | §8.2 | a good retriever has high recall of `F*` "trong ngân sách token hữu hạn"; `Recall@B = \|C ∩ F*\| / \|F*\|` |
| 823 | §8.3 | graph beats text-only retrieval "trong cùng ngân sách context" |
| 839 | §8.3 | condition to check: "context budget hạn chế" |
| 972, 993 | §9.2 | `extract_context_graph(task_anchors, k=2, budget_tokens=12000)` … `return pack_until_budget(ranked, budget_tokens)` |
| 1077 | §10.3 | `get_related_context(anchor_ids, budget_tokens)` |
| 1112 | §10.4 | prompt `repair_with_graph_context` takes `context_budget` |
| 1134 | §10.5 | "timeout và resource limit cho mỗi tool"; audit log of every tool call |
| 88, 1316, 1326 | §2.2 RQ5, §13.2 | token cost, `context token cost`, `LLM token cost` |
| 1391 | §14 Milestone 1 | "return context under token budget" |
| 1475 | §15 | "budgeted subgraph retrieval" against MCP latency |

[P] never names a tokenizer, never says who has the last word on B, and gives no ceiling value beyond §9.2's 12000.

## Two contexts of the budget

The budget plays two different roles, and this spec treats them apart.

| | Offline retrieval evaluation (R1; [P] §8, §13.2 Retrieval) | MCP attached to a real coding agent (RQ5; [P] §10, §13.2 Repair) |
|---|---|---|
| Role of B | experimental control: graph and BM25 are compared "trong cùng ngân sách context" (line 823) | resource limit of one `get_related_context` call (line 1134) |
| Who counts tokens that matter | the evaluation scripts, one counter for every method | the host (Claude Code `/cost`, OpenCode session statistics), with the model's own tokenizer |
| What the server can measure | not involved | size of its own tool results in VGAR units, latency, call counts |
| Needs the model's tokenizer? | no, only the same counter for every method | no: the server never sees the model's real tokens |

Consequences:

- In the agent context, B bounds **one call**, not the agent's total context: the agent may call the tool again or read files with its own tools. Docs must not say "the agent uses only 12000 tokens".
- Per-call metrics of the servers (`*.metrics.jsonl`) are **tool-side** measures (what VGAR sent, in bytes/4 units). Real token cost for RQ5 comes from the host.
- A pinned model tokenizer is needed in neither context, so the MCP servers drop it.

## Problem today

- `get_related_context` fails unless `VGAR_TOKENIZER_MANIFEST` names a verified Qwen tokenizer: `src/vgar/graph/factory.py:56` builds no counter without it and `src/vgar/graph/sqlite_service.py:100` raises `GraphNotReadyError("W5 retrieval requires repository root and a verified tokenizer")`. The README does not ask for the variable, so following it leaves this tool broken.
- A broken manifest stops `vgar-graph` at start-up (`graph_server.py:43`), while `tool_metrics.py` warns and falls back: two behaviours for one variable.
- `budget_tokens` is required and unbounded: the server checks only that it is a positive integer (`retrieval.py:179`).
- Metrics count characters/4 (`approx_chars_div_4`); R1 counts UTF-8 bytes/4 (`FALLBACK:utf8_bytes_ceil_div4`, `evaluation/retrieval/scoring.py:323`).

## Decisions (user, 14/11)

| # | Decision | [P] basis |
|---|---|---|
| D1 | The MCP servers count tokens with one formula, `(len(text.encode("utf-8")) + 3) // 4`, label `FALLBACK:utf8_bytes_ceil_div4`, for packed context and for metrics | no tokenizer in [P]; same counter as R1 so "cùng ngân sách" (line 823) holds between MCP and evaluation |
| D2 | `VGAR_TOKENIZER_MANIFEST` is no longer read by the MCP servers; a host that still sets it is ignored, without a warning | not in [P] |
| D3 | `budget_tokens` of `get_related_context` is optional, default 12000 | line 972 (default), line 1077 (parameter kept; the list marks nothing required), lines 1088–1102 (the one schema example in [P]: the limit `max_depth` has a `default` and is not in `required`) |
| D4 | Server ceiling 12000: effective budget = `min(requested, 12000)` | line 1134 (resource limit per tool), line 972 (value) |
| D5 | A request above the ceiling is clamped, not rejected; the result and the audit log record requested and effective budget | line 1134 (audit log) |
| D6 | Old metric files with `approx_chars_div_4`: README tells the user to rename or delete them before a measured run; no script change | §13.2 needs correct numbers; storage not specified |

Rejected: keeping `$tok` as an optional precision backend (the risk-table row "Toolchain setup nặng → layered design" is about Joern, JARVIS, SCIP, not token counting); default 8000 (M1 decision; the "ARISE (Seddik et al., 2026)" claim pasted on 14/11 is unverified); rejecting over-ceiling requests (costs the agent a turn); a ceiling set by an environment variable (not in [P]).

## Goals

1. With the Quick start configuration (no tokenizer variable), `get_related_context` returns context instead of `GRAPH_NOT_READY`.
2. Context returned by the MCP tool is never above 12000 tokens of the D1 counter, whatever the agent asks.
3. Omitting `budget_tokens` gives 12000.
4. A clamped call says so in its result and its audit record.
5. Metrics and packed context use the same formula and label as R1.

## Non-goals

- No change to the evaluation scripts (`run_graph_retrieval.py`, `run_bm25_retrieval.py`, `run_rt1_ablation.py`, `get_related_context.py`): they keep `--tokenizer-manifest` and their own budgets. `src/vgar/graph/token_counter.py` stays.
- No ceiling or default inside `SQLiteGraphService` or `GraphContextRetriever`: evaluation calls them with other budgets.
- No change to other tools' limits (`limit`, `depth`, `max_hops`, `max_nodes`, test output caps).
- No change to the required parameters `graph_version`, `task_id` of `get_related_context`.
- No new result envelope: the clamp is reported inside the existing `diagnostics`.

## Design

### Counter (D1)

One definition of the formula and label, imported by the MCP code and by `evaluation/retrieval/scoring.py`. Builder's call: move `bytes_div4_counter` and `FALLBACK_COUNTER_LABEL` into `src/vgar/graph/token_counter.py` and have `scoring.py` import them under the same names, so no evaluation caller changes and the servers do not import the evaluation package.

### `src/vgar/graph/factory.py` (D1, D2)

Remove the `VGAR_TOKENIZER_MANIFEST` branch; always pass `count_tokens=bytes_div4_counter, counter_label=FALLBACK_COUNTER_LABEL` to `SQLiteGraphService`. The check at `sqlite_service.py:100` stays and now passes whenever a repository root is set.

### `src/vgar/mcp/tool_metrics.py` (D1, D2)

Remove `_counter()` and the manifest lookup; `token_count(text)` returns `(bytes_div4_counter(text), FALLBACK_COUNTER_LABEL)`. Update the module and function docstrings.

### `src/vgar/mcp/servers/graph_server.py` (D3–D5)

- Constants next to the tool: `DEFAULT_CONTEXT_BUDGET = 12000`, `MAX_CONTEXT_BUDGET = 12000`, each commented with [P] §9.2 line 972 / §10.5 line 1134.
- Signature: `budget_tokens: int = DEFAULT_CONTEXT_BUDGET`. The SDK then publishes it with a default and drops it from `required`. Parameter order may need `budget_tokens` after `task_id`; keyword calls are unaffected (agents call by name).
- Validation: a non-positive or non-integer value is still rejected (`INVALID_LIMIT`, as `retrieval.py:179` does today), before clamping.
- `effective = min(budget_tokens, MAX_CONTEXT_BUDGET)` is passed to `graph_service.get_related_context`.
- Result: `diagnostics.budget = {"requested": budget_tokens, "effective": effective, "ceiling": MAX_CONTEXT_BUDGET, "clamped": budget_tokens > MAX_CONTEXT_BUDGET}`.
- Audit fields: `budget_tokens` stays the requested value; add `effective_budget_tokens`; the summary keeps `item_count`, `total_token_count`.
- Tool docstring (what the agent reads): the budget is optional, defaults to 12000, is capped at 12000, counts UTF-8 bytes/4 (not the model's tokens), and bounds this one call.

### Prompt text

`src/vgar/mcp/proposal/prompts.py:21` says limits "remain enforced by the host/retrieval service". Change to: the server caps `get_related_context` at 12000 tokens (UTF-8 bytes/4). `context_budget` stays a required prompt argument ([P] line 1112).

## Tests (written first)

| Test | Checks |
|---|---|
| factory without `VGAR_TOKENIZER_MANIFEST` | service has a counter with label `FALLBACK:utf8_bytes_ceil_div4`; `get_related_context` on a built fixture graph returns items |
| factory with `VGAR_TOKENIZER_MANIFEST` set to a missing file | server still builds; label unchanged (D2) |
| tool, `budget_tokens` omitted | `diagnostics.budget == {"requested": 12000, "effective": 12000, "ceiling": 12000, "clamped": False}`; `total_token_count <= 12000` |
| tool, `budget_tokens=50000` | effective 12000, `clamped: True`; `total_token_count <= 12000`; audit record has requested 50000 and effective 12000 |
| tool, `budget_tokens=4000` | effective 4000, `total_token_count <= 4000` |
| tool, `budget_tokens=0` / `-1` | `INVALID_LIMIT` as today |
| tool schema | `budget_tokens` has default 12000 and is not in `required` |
| metrics | `token_count("abcdefgh") == (2, "FALLBACK:utf8_bytes_ceil_div4")`; a non-ASCII string counts bytes, not characters |
| evaluation import | `scoring.bytes_div4_counter` and `scoring.FALLBACK_COUNTER_LABEL` still importable and identical |

Existing tests that assert `approx_chars_div_4` (`tests/mcp_server/test_tv2_tool_metrics.py:37`, fixtures at lines 80, 82) are updated. Full suite before and after; known failures stay the same.

## Docs

- `README.md`: remove `VGAR_TOKENIZER_MANIFEST` from the environment table; in "Token usage and latency", counts are UTF-8 bytes/4 tool-side measures and real model tokens come from the host; rename or delete old metric files before a measured run (D6); one paragraph on the budget: optional, default and ceiling 12000, bounds one call.
- `docs/mcp_server/debugging.md:35`: `token_method` is `FALLBACK:utf8_bytes_ceil_div4`.
- `docs/mcp_server/tools.md`: `get_related_context` budget default, ceiling, `diagnostics.budget`.

## Builder's calls (open to correction)

- Location of the shared counter (`token_counter.py`).
- Field name `diagnostics.budget` and its four keys.
- Constants in `graph_server.py`, not in `configs/mcp_server/runtime.json`, matching `PYTEST_TIMEOUT_SECONDS` as a server constant.
