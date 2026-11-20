# Harness đo toàn bộ layer (TV2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đo từng layer của graph theo §13.1–13.3 trên profile thêm dần, offline (T1) và với Qwen điều hướng graph (T2), trên cùng một graph SQLite cho mỗi (task, bản dựng).

**Architecture:** Thư mục mới `baseline/` chỉ import từ `src/vgar`, `ablation_matrix/`, `scripts/`. Bốn bản dựng graph (`base`, `scip`, `scip_lsp`, `full`) dựng qua `runner.load_or_build_graph` rồi lưu SQLite; T1 ghép các hàm chấm điểm R1 với F\*_core v2; T2 là vòng agent tự viết (Qwen 4-bit qua HF transformers) gọi tool đọc file và tool của server graph qua MCP SDK 2.2 stdio.

**Tech Stack:** Python 3.11, pytest, MCP SDK 2.2.0 (client stdio), transformers + bitsandbytes (nf4), SQLite (`SQLiteGraphStore`).

**Spec:** `docs/superpowers/specs/2026-11-19-tv2-layer-harness-design.md`

## Global Constraints

- Không sửa file nào trong `src/`, `ablation_matrix/`, `scripts/`; mọi code mới trong `baseline/`.
- Graph cache: `~/rt1/graphs/<build>/<instance_id>.db`, một DB cho mỗi (task, bản dựng).
- Model `Qwen/Qwen3-4B-Instruct-2507`, 4-bit nf4, greedy (temperature 0).
- Giới hạn T2: tối đa 12 lời gọi tool, ≤ 1500 token mỗi kết quả tool, ngữ cảnh ≤ 16k token, `get_related_context` ngân sách 3000.
- Token đếm bằng `bytes_div4_counter` (`FALLBACK_COUNTER_LABEL`) như R1.
- Chỉ tập dev (`require_split(manifest, allowed=("dev",), protocol="r1")`).
- Thứ hạng của mọi cánh được tính **trước** khi đọc patch gold (giữ bất biến của R1).
- Người dùng tự commit, tự cài gói và tự chạy mọi lượt dài/GPU.

## Review Focus

- Profile cần bản dựng `scip`/`full` nhưng thiếu đường dẫn công cụ → báo lỗi rõ tên biến, không im lặng rơi về graph `base` (test ở Task 2).
- DB cache đã tồn tại nhưng dựng bằng code cũ (builder hash khác) → dựng lại, không dùng nhầm (test ở Task 3).
- `--resume` khi task đã có một số profile → chỉ tính profile còn thiếu, giữ nguyên số cũ (test ở Task 4).
- Qwen trả `<tool_call>` hỏng JSON, gọi tool không tồn tại, hoặc không bao giờ trả JSON cuối → task vẫn nằm trong mẫu số với trạng thái lỗi (test ở Task 7).
- Tool đọc file nhận đường dẫn `../` hoặc tuyệt đối ra ngoài cây mã → từ chối (test ở Task 6).

## Không có trong kế hoạch này

- Profile phụ `A2+H` (lịch sử GraphDiff): cần clone git từng task; làm sau bằng cờ `--history` sẵn có của R1.
- F\*_ext (coverage runtime) và recall cạnh từ trace runtime: giai đoạn sau (cần Docker chạy test).

## Bản đồ file

| File | Trách nhiệm |
|---|---|
| `baseline/__init__.py` | rỗng |
| `baseline/_paths.py` | thêm `ROOT/src`, `ROOT/ablation_matrix`, `ROOT/scripts` vào `sys.path` |
| `baseline/conftest.py` | `import baseline._paths` cho pytest |
| `baseline/frontier_v2.py` | F\*_core v2 |
| `baseline/profiles.py` | bản dựng → `LayerConfigs`; profile → (bản dựng, cánh) |
| `baseline/graph_store.py` | dựng hoặc nạp graph SQLite |
| `baseline/run_offline.py` | T1 |
| `baseline/report.py` | bảng theo layer (T0 G1, T1, T2) |
| `baseline/nav/tools.py` | tool đọc file, client MCP graph, cắt kết quả, ghi đoạn đã đọc |
| `baseline/nav/model.py` | nạp Qwen 4-bit, sinh, tách `<tool_call>` và JSON cuối |
| `baseline/nav/spike_qwen_speed.py` | spike đo tốc độ (bỏ đi) |
| `baseline/nav/run_nav.py` | T2: vòng lặp, chấm, CLI |
| `baseline/tests/test_*.py` | test từng file trên |

Lệnh test chung (Windows): `.venv/Scripts/python.exe -m pytest baseline/tests -q -p no:cacheprovider`

---

### Task 1: Khung thư mục và F\*_core v2

**Files:**
- Create: `baseline/__init__.py`, `baseline/_paths.py`, `baseline/conftest.py`, `baseline/frontier_v2.py`
- Test: `baseline/tests/test_frontier_v2.py`

**Interfaces:**
- Produces: `changed_code_names(patch: str) -> set[str]`; `frontier_core_v2(patch: str, gold: Mapping[str, Any], corpus: CorpusIndex) -> list[str]` (id hàm đã sắp xếp).

- [ ] **Step 1: Viết test** (dùng `CorpusIndex` của `vgar.evaluation.retrieval.scoring`, như `tests/m2/test_resolver_comparison.py`)

```python
def test_removed_line_names_join_the_frontier():
    corpus = CorpusIndex({"src/a.py": "def old_helper():\n    return 1\n\ndef new_helper():\n    return 2\n",
                          "src/b.py": "def run():\n    return old_helper()\n"})
    run_id = corpus.definitions["src/b.py"][0]["parent_id"]
    patch = ("--- a/src/b.py\n+++ b/src/b.py\n@@ -2 +2 @@\n-    return old_helper()\n+    return new_helper()\n")
    ids = {d["symbol"].rsplit(".", 1)[-1]: d["parent_id"] for v in corpus.definitions.values() for d in v}
    assert frontier_core_v2(patch, {"gold_functions": [run_id]}, corpus) == sorted({run_id, ids["old_helper"], ids["new_helper"]})

def test_comments_strings_and_ambiguous_names_stay_out():
    # "dup" is defined twice; "ghost" appears only in a comment and a string
    ...assert ids["dup"] not in result and ids["ghost"] not in result

def test_deleted_file_lines_count():  # "+++ /dev/null": path comes from "--- a/<path>"
    ...
```

- [ ] **Step 2:** Chạy `... -k frontier_v2` → FAIL (`ModuleNotFoundError: baseline.frontier_v2`).
- [ ] **Step 3:** Cài. `changed_code_names`: theo header `--- a/<p>` và `+++ b/<p>` (lấy đường dẫn `b/` khi có, nếu `+++ /dev/null` thì giữ đường dẫn `a/`), gom tên trên dòng bắt đầu bằng `+` hoặc `-` (trừ `+++`, `---`) của file `is_source`, dùng `vgar.evaluation.retrieval.frontier._name_tokens` và trừ `_SKIP`. `frontier_core_v2` = `gold_functions` ∪ định nghĩa duy nhất theo tên ngắn (giống `dependency_frontier`).
- [ ] **Step 4:** Chạy lại → PASS.
- [ ] **Step 5:** Ghi ledger; người dùng commit `baseline/__init__.py baseline/_paths.py baseline/conftest.py baseline/frontier_v2.py baseline/tests/test_frontier_v2.py`.

---

### Task 2: Profile và bản dựng

**Files:**
- Create: `baseline/profiles.py`
- Test: `baseline/tests/test_profiles.py`

**Interfaces:**
- Produces:
  - `BUILDS = ("base", "scip", "scip_lsp", "full")`
  - `PROFILES: dict[str, tuple[str, str]]` = `{"P0": ("base", "ast_no_task_trace"), "A1": ("base", "no_task_trace"), "A2": ("base", "task_trace"), "A3": ("base", "a3"), "A3_scip": ("scip", "a3"), "A3_scip_lsp": ("scip_lsp", "a3"), "full": ("full", "a3")}`
  - `PROFILE_ORDER = tuple(PROFILES)` (thứ tự thêm dần)
  - `build_env(build: str, tools: Mapping[str, str]) -> dict[str, str]` và `build_layers(build: str, tools: Mapping[str, str]) -> LayerConfigs` = `layer_config.layer_configs(build_env(...))`.
  - `tools` dùng đúng tên biến host: `VGAR_NODE`, `VGAR_SCIP_ENTRY`, `VGAR_SCIP_TIMEOUT`, `VGAR_LSP_ENTRY`, `VGAR_TSG_EXECUTABLE`, `VGAR_TSG_TREE_SITTER_DIR`. Bản dựng: `base` = `{}`; `scip` = node + SCIP; `scip_lsp` = + LSP; `full` = + TSG + `VGAR_JOERN=1` + `VGAR_JARVIS=1`.

- [ ] **Step 1: Viết test**

```python
def test_every_profile_names_a_known_build_and_arm():
    from retrieval_variants import GRAPH_ARM_SPECS
    assert all(build in BUILDS and arm in GRAPH_ARM_SPECS for build, arm in PROFILES.values())
    assert PROFILE_ORDER[0] == "P0" and PROFILE_ORDER[-1] == "full"

def test_builds_add_layers_cumulatively(tmp_path):
    tools = {name: str(tmp_path / name) for name in ("VGAR_NODE", "VGAR_SCIP_ENTRY", "VGAR_LSP_ENTRY",
             "VGAR_TSG_EXECUTABLE", "VGAR_TSG_TREE_SITTER_DIR")}
    assert not build_layers("base", tools).any_optional
    scip = build_layers("scip", tools); assert scip.scip and not scip.lsp
    full = build_layers("full", tools); assert full.scip and full.lsp and full.tsg and full.joern and full.jarvis

def test_missing_tool_for_a_build_names_the_variable():
    with pytest.raises(ValueError, match="VGAR_SCIP_ENTRY"):
        build_layers("scip", {})
```

- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài; `build_env` raise `ValueError(f"build {build!r} needs {name}")` cho biến bắt buộc còn thiếu.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Ledger; người dùng commit `baseline/profiles.py baseline/tests/test_profiles.py`.

---

### Task 3: Graph SQLite cho mỗi (task, bản dựng)

**Files:**
- Create: `baseline/graph_store.py`
- Test: `baseline/tests/test_graph_store.py`

**Interfaces:**
- Consumes: `build_layers` (Task 2).
- Produces:
  - `graph_db_path(graphs_dir: Path, build: str, instance_id: str) -> Path`
  - `load_or_build(root: Path, row: dict, tree: Path, *, build: str, layers: LayerConfigs, graphs_dir: Path, builder_hash: str) -> tuple[dict, dict]` → `(document, meta)`, `meta = {"build", "db", "graph_version", "build_seconds", "from_cache", "builder_hash", "layer_status"}`.

- [ ] **Step 1: Viết test** (cây mã nhỏ 2 file trong `tmp_path`, `row = {"instance_id": "o__r-1", "repo": "o/r", "base_commit": "c"*40}`)

```python
def test_second_call_reads_the_same_graph_from_sqlite(tmp_path): ...
    first_doc, first = load_or_build(...); second_doc, second = load_or_build(...)
    assert not first["from_cache"] and second["from_cache"] and first["db"].exists()
    assert second_doc["graph_version"] == first_doc["graph_version"]
    assert len(second_doc["nodes"]) == len(first_doc["nodes"]) and second["build_seconds"] == first["build_seconds"]

def test_new_builder_hash_rebuilds(tmp_path): ...   # builder_hash="h2" → from_cache False

def test_builds_use_separate_databases(tmp_path):
    assert graph_db_path(tmp_path, "base", "x") != graph_db_path(tmp_path, "scip", "x")
```

- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài. Dựng bằng `run_graph_retrieval.load_or_build_graph(root, row, tree, rebuild=True, builder_hash=builder_hash, cache=False, layers=layers)` (cùng đường với R1); ghi `SQLiteGraphStore(db).initialize()` + `.ingest(document)`; ghi `meta` (trừ `from_cache`) vào `<db>.meta.json`. Nạp khi DB và meta tồn tại **và** `meta["builder_hash"] == builder_hash`: `SQLiteGraphStore(db, graph_version=meta["graph_version"]).load_document(meta["graph_version"])`. Khác hash thì xóa DB cũ của đúng đường dẫn đó và dựng lại. `layer_status` lấy từ `layer_summary(document, layers)` khi `layers.any_optional`, ngược lại `{}`.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Ledger; người dùng commit `baseline/graph_store.py baseline/tests/test_graph_store.py`.

---

### Task 4: T1 — chạy offline theo profile

**Files:**
- Create: `baseline/run_offline.py`
- Test: `baseline/tests/test_run_offline.py`

**Interfaces:**
- Consumes: `frontier_core_v2` (Task 1), `PROFILES`, `build_layers` (Task 2), `load_or_build` (Task 3); từ repo: `variant_outputs`, `graph_rank`, `extract_gold`, `score_record`, `flat_metrics`, `native_context_metrics`, `component_metrics`, `make_include`, `CorpusIndex`, `bm25_rank`, `grep_rank`, `neighbor_rank`, `run_r1_ablation._text_arm`, `gold_impact.cross_file_reach`, `gold_impact.filter_patch`.
- Produces:
  - `evaluate_profiles(row: dict, sources: dict[str, str], tree: Path, documents: dict[str, dict], profiles: list[str], *, counter, label: str, budget_tokens: int, with_text: bool) -> dict`
  - Kết quả mỗi task (một run duy nhất, profile là tên cánh, để `compare_runs --arms-vs` dùng được):
    `{"instance_id", "status": "SUCCEEDED", "cross_file": bool, "gold": {...frontier_functions: F*_core v2...}, "arms": {<profile>: {"metrics", "ranked", "anchors", "diagnostics"}, "bm25"|"grep"|"neighbor": {...}}, "impact": {<build>: cross_file_reach rows}, "graphs": {<build>: meta}}`
  - **Lệch có chủ ý so với spec §7 bước 6:** một run duy nhất `DIR/tasks/<id>.json` với profile là tên cánh (thay vì `<profile>/tasks/`), để `compare_runs --arms-vs` so được các profile trong cùng task.
  - CLI: `python baseline/run_offline.py ROOT MANIFEST --out DIR [--profiles P0,A1,...] [--only ids.txt] [--resume] [--graphs-dir ~/rt1/graphs] [--budget-tokens 12000] [--node ...] [--scip-entry ...] [--scip-timeout 900] [--lsp-entry ...] [--tsg-executable ... --tsg-tree-sitter-dir ...]`. Ghi `DIR/tasks/<instance_id>.json`.

- [ ] **Step 1: Viết test** (cây mã nhỏ: `pkg/a.py` có `f`, `pkg/b.py` gọi `f`; patch gold sửa cả hai file; `documents = {"base": PythonGraphBuilder(...).build(tree)}`)

```python
def test_profiles_share_one_gold_with_frontier_v2_and_report_served_context(tmp_path): ...
    out = evaluate_profiles(row, sources, tree, documents, ["P0", "A1", "A2", "A3"], counter=bytes_div4_counter,
                            label=FALLBACK_COUNTER_LABEL, budget_tokens=4000, with_text=True)
    assert set(out["arms"]) == {"P0", "A1", "A2", "A3", "bm25", "grep", "neighbor"}
    assert out["gold"]["frontier_functions"] == frontier_core_v2(row["patch"], out["gold"], CorpusIndex(sources))
    assert "native_frontier_in_context" in out["arms"]["A2"]["metrics"] and out["cross_file"] is True
    assert set(out["impact"]) == {"base"}

def test_ranking_is_frozen_before_gold(tmp_path, monkeypatch):
    # extract_gold patched to raise if called before every graph_rank finished → no raise
    ...

def test_resume_computes_only_missing_profiles(tmp_path): ...
    # task file already has arms P0, A1 with sentinel metrics; run_offline_task(..., ["P0","A1","A2"], resume=True)
    # → sentinel kept, A2 added, text arms not recomputed
```

- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài `evaluate_profiles`, theo thứ tự: (a) mỗi bản dựng một lần `variant_outputs(document, tree, issue, include=make_include(corpus), count_tokens=counter, counter_label=label, budget_tokens=budget_tokens, arms=<các cánh của profile thuộc bản dựng>)`; (b) `graph_rank` cho từng profile, và các bản ghi baseline văn bản; (c) **sau đó** `extract_gold` + `frontier_core_v2` (khi `function_labels_complete`); (d) chấm bằng `score_record` → `flat_metrics` + `native_context_metrics(context, gold, corpus)` + `component_metrics`; (e) `cross_file = len(gold["gold_files"]) >= 2`; nếu đúng thì `impact[build] = cross_file_reach(filter_patch(patch, set(gold["gold_files"]))[0], document, tree)`. Cài `run_offline_task(root, row, profiles, tools, *, out_dir, graphs_dir, builder_hash, budget_tokens, resume) -> dict` (đọc/ghi file, `--resume` chỉ tính profile thiếu) và `main` (lấy cây mã như R1: `read_repository_sources`, `extract_python_tree`; `runner.source_fingerprint(ROOT)["digest"]` làm `builder_hash`; mỗi lỗi task ghi `{"status": "ERROR", "reason"}`).
- [ ] **Step 4:** PASS; thêm chạy `baseline/tests` toàn bộ → PASS.
- [ ] **Step 5:** Ledger; người dùng commit `baseline/run_offline.py baseline/tests/test_run_offline.py`.
- [ ] **Step 6 (người dùng, WSL, khoảng 15–25 phút):**

```bash
cd /mnt/d/kltn/vgar_mcp_mvp_demo && PYTHONPATH=src ~/.vgar-wsl/bin/python baseline/run_offline.py \
  ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json --out ~/rt1/results/layers --profiles P0,A1,A2,A3 \
  2>&1 | tee ~/rt1/layers_base.log
```
Expected: 50 dòng `SUCCEEDED`, `~/rt1/graphs/base/*.db` có 50 file.

---

### Task 5: Báo cáo theo layer

**Files:**
- Create: `baseline/report.py`
- Test: `baseline/tests/test_report.py`

**Interfaces:**
- Consumes: `PROFILE_ORDER` (Task 2); `compare_runs.load`, `compare_runs.compare_arms` (đã có `min_gold_files`).
- Produces: `layer_table(run_dir: Path, metrics: list[str], min_gold_files: int = 0) -> str` (markdown: mỗi profile có trong run, giá trị trung bình và chênh lệch so với profile **liền trước có mặt** kèm CI 95% và thắng/thua); `g1_table(g1_json: Path) -> str` (mỗi cấu hình: `calls.calls_only` và `calls.with_may_call` precision/recall + CI); `nav_table(nav_dir: Path) -> str` (Task 7); CLI `python baseline/report.py --layers DIR [--g1 FILE ...] [--t0-link NAME=PATH ...] [--nav DIR] --out FILE.md` (các báo cáo T0 khác như TR-1, GD1, U1 chỉ được liệt kê kèm đường dẫn, không đọc số) in kèm lệnh tái tạo đã ghi trong từng run.

- [ ] **Step 1: Viết test** với JSON tổng hợp trong `tmp_path` (2 task, profile A1/A2, một task 2 file gold): bảng có dòng `A2` với chênh lệch so với `A1`; `min_gold_files=2` chỉ còn 1 task; `g1_table` đọc đúng `recall` 0.418 từ JSON mẫu dạng `{"configurations": {"static": {"status": "ok", "calls": {"calls_only": {...}, "with_may_call": {...}}}}}`.
- [ ] **Step 2:** FAIL. **Step 3:** Cài. **Step 4:** PASS.
- [ ] **Step 5:** Ledger; người dùng commit `baseline/report.py baseline/tests/test_report.py`.

---

### Task 6: Tool cho T2 (đọc file + client MCP graph)

**Files:**
- Create: `baseline/nav/__init__.py`, `baseline/nav/tools.py`
- Test: `baseline/tests/test_nav_tools.py`

**Interfaces:**
- Produces:
  - `ToolResult(text: str, spans: list[tuple[str, int, int]])` (dataclass; `spans` = đoạn code (đường dẫn, dòng đầu, dòng cuối) Qwen đã thấy).
  - `cap_tokens(text: str, limit: int = 1500) -> str` (cắt theo bytes/4, thêm dòng `[truncated]`).
  - `FileTools(tree: Path)`: `grep(pattern: str, glob: str = "**/*.py") -> ToolResult` (tối đa 50 dòng khớp, `path:line: text`), `read_file(path: str, start: int = 1, end: int | None = None) -> ToolResult` (tối đa 200 dòng), `list_dir(path: str = ".") -> ToolResult`; `schemas() -> list[dict]` (dạng function-schema cho chat template).
  - `GraphTools(tree: Path, db: Path, graph_version: str, task_id: str, audit_log: Path)`: async context manager mở server bằng `StdioServerParameters(command=sys.executable, args=["-m", "vgar.mcp.servers.graph_server"], env={"PYTHONPATH": str(ROOT / "src"), "VGAR_REPOSITORY_ROOT": str(tree), "VGAR_GRAPH_DATABASE": str(db), "VGAR_MCP_AUDIT_LOG": str(audit_log)})`; `TOOLS = ("search_symbols", "find_task_anchors", "get_related_context", "get_callers", "get_callees", "explain_dependency_path")`; `schemas()` lấy từ `session.list_tools()`, bỏ `graph_version`, `task_id` khỏi schema; `async call(name, arguments) -> ToolResult` điền lại hai tham số đó, `get_related_context` mặc định `budget_tokens=3000`, `spans` lấy từ `items[].range` khi có.

- [ ] **Step 1: Viết test**

```python
def test_read_file_refuses_paths_outside_the_tree(tmp_path):
    tools = FileTools(tmp_path); (tmp_path / "a.py").write_text("x = 1\n")
    assert "refused" in tools.read_file("../secret.py").text and tools.read_file("/etc/passwd").spans == []

def test_read_file_records_the_span_it_showed(tmp_path): ...   # read_file("a.py", 1, 1).spans == [("a.py", 1, 1)]

def test_cap_tokens_marks_truncation(): assert cap_tokens("x" * 10000, 100).endswith("[truncated]")

def test_graph_tools_prebind_version_and_task(tmp_path): ...
    # anyio.run: tiny repo → PythonGraphBuilder → SQLiteGraphStore ingest → GraphTools(...)
    # "graph_version" not in any schema's properties; call("search_symbols", {"query": "f"}).text mentions "pkg/a.py"
```

- [ ] **Step 2:** FAIL. **Step 3:** Cài. **Step 4:** PASS (test MCP chạy được trên Windows `.venv` vì đã có `mcp` 2.2.0).
- [ ] **Step 5:** Ledger; người dùng commit `baseline/nav/__init__.py baseline/nav/tools.py baseline/tests/test_nav_tools.py`.

---

### Task 7: Model Qwen, spike tốc độ và vòng T2

**Files:**
- Create: `baseline/nav/model.py`, `baseline/nav/spike_qwen_speed.py`, `baseline/nav/run_nav.py`
- Test: `baseline/tests/test_nav_model.py`, `baseline/tests/test_run_nav.py`

**Interfaces:**
- Consumes: `FileTools`, `GraphTools`, `ToolResult`, `cap_tokens` (Task 6); `load_or_build`, `graph_db_path` (Task 3); `frontier_core_v2` (Task 1); `extract_gold`, `score_record`, `flat_metrics`, `RankItem`, `RankRecord`, `CorpusIndex`.
- Produces:
  - `parse_tool_calls(text: str) -> list[dict]` (khối `<tool_call>{"name":..., "arguments":{...}}</tool_call>`; JSON hỏng → phần tử `{"error": "..."}`); `parse_final(text: str) -> dict | None` (JSON có `files` và/hoặc `functions`, cắt còn 5 và 10).
  - `QwenModel(model_id: str = "Qwen/Qwen3-4B-Instruct-2507", revision: str | None = None)`: nạp `AutoModelForCausalLM` với `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16)`, `device_map="cuda"`; `generate(messages: list[dict], tools: list[dict], max_new_tokens: int = 1024) -> tuple[str, dict]` (greedy; trả text và `{"prompt_tokens", "completion_tokens", "seconds"}`).
  - `run_task(model, tools: dict[str, Callable], schemas: list[dict], row: dict, *, max_calls: int = 12, max_context_tokens: int = 16000) -> dict` → `{"status": "OK"|"NO_ANSWER"|"BAD_ANSWER"|"CONTEXT_FULL", "answer", "turns": [...], "tool_calls": [{"name", "seconds", "tokens", "error"}], "spans": [...], "usage": {...}}`.
  - `score_nav(result: dict, row: dict, sources: dict[str, str]) -> dict` → `flat_metrics` của danh sách cuối + `seen_frontier_recall`, `seen_all_gold_files`, `non_gold_files_read`, `tool_calls`, `mean_tool_seconds`, `prompt_tokens`, `completion_tokens`.
  - CLI `python baseline/nav/run_nav.py ROOT MANIFEST --out DIR --arms base,graph_v0[,graph_v0_scip] [--only ids.txt] [--limit N] [--resume] [--graphs-dir ~/rt1/graphs]`; `graph_v0` dùng DB `base`, `graph_v0_scip` dùng DB `scip` (phải có sẵn từ Task 4); ghi `DIR/<arm>/<instance_id>.json`. Prompt hệ thống một hằng số `SYSTEM_PROMPT` chung cho mọi cánh: "Tìm các file và hàm cần sửa để giải quyết issue; dùng tool để đọc repo; kết thúc bằng một JSON `{\"files\": [...], \"functions\": [\"path::Qualified.name\", ...]}`".

- [ ] **Step 1: Viết test parse** (`test_nav_model.py`): một/hai `<tool_call>` hợp lệ; JSON hỏng → `{"error"}`; `parse_final` nhận JSON trong khối ```json; không có JSON → `None`.
- [ ] **Step 2:** FAIL. **Step 3:** Cài `parse_tool_calls`, `parse_final`, `QwenModel` (phần nạp model không có test đơn vị; spike kiểm). **Step 4:** PASS.
- [ ] **Step 5 (người dùng, WSL): cài môi trường và chạy spike**

```bash
~/.vgar-wsl/bin/pip install "mcp==2.2.0" bitsandbytes accelerate
~/.vgar-wsl/bin/python -c "import torch; print(torch.cuda.is_available())"     # phải in True
~/.vgar-wsl/bin/huggingface-cli download Qwen/Qwen3-4B-Instruct-2507
cd /mnt/d/kltn/vgar_mcp_mvp_demo && PYTHONPATH=src ~/.vgar-wsl/bin/python baseline/nav/spike_qwen_speed.py
```
`spike_qwen_speed.py`: nạp `QwenModel`, một hội thoại có schema `read_file`, in `seconds`, số token, `torch.cuda.max_memory_allocated()`, và `parse_tool_calls` của câu trả lời. Expected: có một tool call hợp lệ; ghi lại giây/lượt. Nếu ước tính > 2 phút/task (12 lượt), dừng và quay lại thiết kế (phương án B).

- [ ] **Step 6: Viết test vòng lặp** (`test_run_nav.py`) với `FakeModel` trả lần lượt các chuỗi định sẵn và tool giả:

```python
def test_loop_calls_tools_then_scores_the_final_answer(): ...   # status "OK", 2 tool_calls, spans gộp
def test_unknown_tool_and_bad_json_are_reported_not_fatal(): ...   # tool_calls[i]["error"] set, loop continues
def test_no_final_answer_after_max_calls_keeps_the_task(): ...    # status "NO_ANSWER", score_nav gives 0 recall, not missing
def test_seen_frontier_counts_functions_inside_read_spans(): ...  # span covering whole def → counted
```

- [ ] **Step 7:** FAIL. **Step 8:** Cài `run_task`, `score_nav` (map `path::Qualified.name` sang `CorpusIndex.definitions` theo đường dẫn + symbol; không khớp → `unmapped`), CLI (mỗi task: lấy cây mã như Task 4, `load_or_build` với bản dựng của cánh, mở `GraphTools` nếu cánh có graph, nạp model **một lần** cho cả lượt). **Step 9:** PASS + toàn bộ `baseline/tests` PASS.
- [ ] **Step 10:** Ledger; người dùng commit `baseline/nav/model.py baseline/nav/spike_qwen_speed.py baseline/nav/run_nav.py baseline/tests/test_nav_model.py baseline/tests/test_run_nav.py`.
- [ ] **Step 11 (người dùng, WSL): thử 10 task rồi 50 task**

```bash
head -10 ~/rt1/all50.txt > ~/rt1/nav10.txt
cd /mnt/d/kltn/vgar_mcp_mvp_demo && PYTHONPATH=src ~/.vgar-wsl/bin/python baseline/nav/run_nav.py \
  ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json --out ~/rt1/results/nav --arms base,graph_v0 \
  --only ~/rt1/nav10.txt 2>&1 | tee ~/rt1/nav10.log
```
Expected: 20 file kết quả; tỉ lệ `NO_ANSWER`/`BAD_ANSWER` được báo cáo. Sau khi người dùng xem 10 task, chạy lại không có `--only` và có `--resume`.

---

### Task 8: Bản dựng SCIP, LSP, Full (chạy, không code mới)

- [ ] **Step 1 (người dùng, WSL):** chạy Task 4 với `--profiles A3_scip,A3_scip_lsp --resume` và các tùy chọn `--node ~/vgar-tools/node-big --scip-entry ~/vgar-tools/node_modules/@sourcegraph/scip-python/index.js --scip-timeout 2700 --lsp-entry <langserver>` (cùng `NODE_OPTIONS=--max-old-space-size=6144`, `ulimit -s 65536` như G1). Expected: profile mới được thêm vào file task cũ; trạng thái layer ghi trong `graphs`.
- [ ] **Step 2:** `--profiles full --resume` khi Docker bật; nếu quá chậm thì dùng `--only` một phần task và ghi rõ số task.
- [ ] **Step 3:** T2 cánh `graph_v0_scip` trên 50 task (`--arms graph_v0_scip --resume`).
- [ ] **Step 4:** `baseline/report.py --layers ~/rt1/results/layers --g1 ~/rt1/g1/report_scip4/g1_report.json --nav ~/rt1/results/nav --out docs/status/tv2_layer_harness_<ngày>.md`; người dùng commit báo cáo.

---

### Task 9: Cánh `graph_conf` (sau khi `graph_v0` ổn định)

**Files:**
- Modify: `baseline/nav/tools.py` (lớp `GraphTools`), `baseline/nav/run_nav.py` (cánh mới)
- Test: `baseline/tests/test_nav_tools.py`

**Interfaces:**
- Produces: `GraphTools(..., with_confidence: bool = False)`; khi bật, kết quả `get_callers`/`get_callees` mỗi symbol có thêm `edge_confidence` và `edge_provenance` đọc từ bảng cạnh `CALLS` của cùng DB (chỉ đọc, `sqlite3` với `mode=ro`), sắp theo confidence giảm dần; cánh `graph_conf` = `graph_v0` + `with_confidence=True`.

- [ ] **Step 1:** Test: DB nhỏ có hai cạnh `CALLS` với confidence 0.9 và 0.5 → kết quả có `edge_confidence` và thứ tự 0.9 trước 0.5; tắt cờ thì kết quả giống `graph_v0`.
- [ ] **Step 2:** FAIL. **Step 3:** Cài (tên cột lấy từ schema bảng cạnh trong `vgar/graph/sqlite_store.py`). **Step 4:** PASS.
- [ ] **Step 5:** Ledger; người dùng commit; người dùng chạy `--arms graph_conf --resume` trên 50 task; cập nhật báo cáo.
