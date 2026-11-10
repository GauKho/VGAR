# TV2 · RT-1: retrieval đủ 6 đặc trưng Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `GraphContextRetriever` dùng được `G_arch` (`components_depending_on`, Port), `MAY_CALL` có giảm điểm, `TRACES_TO` của TR-1 và `public_api_risk` theo Port, mỗi thứ sau một cờ tắt mặc định; đo từng cờ so với cấu hình mặc định trên bộ dev 50 task rồi chốt `RT1_CONFIG`.

**Architecture:** Cờ mới nằm trong `RetrievalConfig`; `ranking_config_hash` bỏ qua cờ đang ở giá trị tắt, nên `RetrievalConfig()` giữ đúng `FROZEN_RANKING_HASH`. Mỗi cờ chỉ thêm ứng viên hoặc đổi confidence trước/sau `_walk`, không đổi thuật toán duyệt. Đo bằng một script điều phối mới, gọi lại các hàm của `run_graph_retrieval.py` và xóa dữ liệu từng task sau khi đo.

**Tech Stack:** Python 3.11+, pytest, pyarrow (đã có, đọc parquet), thư viện chuẩn. Không thêm thư viện.

**Spec:** `docs/superpowers/specs/2026-11-10-tv2-rt-1-retrieval-design.md`

## Global Constraints

- Căn cứ: chỉ plan 2 tuần, proposal và các file context; code có sẵn chỉ là hiện trạng.
- `RetrievalConfig()` mặc định cho đúng kết quả cũ; `ranking_config_hash(RetrievalConfig()) == "sha256:993f02c962dde7b1d506497798b44bcc4316ed5b5d64a9c84c5ab2a296bbb14a"`. Không sửa `FROZEN_RANKING_HASH` ở `evaluation/dry_run.py` và `tests/test_graph_retrieval.py`.
- Cờ mới và giá trị tắt: `use_component_dependents=False`, `dependent_symbols_per_component=3`, `may_call_factor=0.0`, `use_trace_component=False`, `public_api_from_ports=False`.
- Ngưỡng trace: chỉ dùng `TRACES_TO` xếp đầu theo `rank_component_traces` khi `confidence >= 0.7`; seed từ trace và component có confidence `0.45`.
- Không đặc trưng nào đọc dữ liệu sau `base_commit`, patch gold hay `FAIL_TO_PASS` (arm `graph_f2p` vẫn dùng `FAIL_TO_PASS` như giao thức cũ). Chỉnh tham số chỉ trên dev; không chạy held-out.
- `recent_change_frequency` giữ "unavailable" khi không có `change_counts` (spec §4.5, C). Không sửa code MCP của TV1 (spec §4.6).
- Quy tắc MCP build-server cho code mới trong `src`: không ghi stdout, logger theo module (`logging.getLogger(__name__)`), docstring có mục `Args`.
- Đo: ngân sách `--budget-tokens 12000` ([P] 972); `may_call_factor` ∈ {0,5; 1,0}; không dò thêm mức. RT-1 chỉ so với cấu hình mặc định; so với BM25 và các baseline khác thuộc R1 (spec §2, §5).
- **Không `git commit`, không `git push`.** Mỗi task kết thúc bằng danh sách file cho người dùng tự commit. Không đưa `artifacts/sample_graph.db`, file lạ `olve --agent ...`, `tests/fixtures/vgar-demo-shop/` vào commit. Không sửa `src` khi suite đang chạy.
- Lệnh test: `python -m pytest -q -p no:cacheprovider <file>`. Test RT-1 chạy trên Windows và WSL (`~/vgar-venv`, Python 3.11).

## Review Focus

1. Overlay có anchor nhưng graph không có Component, Port hay `MAY_CALL` (repo phẳng, graph cũ): mọi cờ bật vẫn chạy, không lỗi, kết quả bằng khi tắt (Task 2, Task 3, Task 4).
2. Bộ lọc `include` của pipeline đánh giá (bỏ file test, file ngoài corpus): ứng viên mới từ component, trace, `MAY_CALL` cũng phải qua `include` (Task 2, Task 4).
3. Hai lần chạy cùng đầu vào cho cùng danh sách ứng viên và thứ tự, kể cả khi hai Component có cùng confidence (Task 4).
4. Script đo bị ngắt giữa chừng: `--resume` không chạy lại task đã có kết quả và không ghi đè kết quả cũ (Task 7).
5. `--prune` chỉ xóa đúng archive, cây mã nguồn và graph của task vừa đo, không xóa thư mục kết quả hay dữ liệu task khác (Task 7).

---

### Task 1: Cờ mới và hash ổn định

**Files:** Modify `src/vgar/graph/retrieval.py:34-73`. Test `tests/test_retrieval_rt1.py` (tạo mới).

**Interfaces — Produces:**

```python
# RetrievalConfig thêm 5 trường (giá trị tắt ở Global Constraints)
RT1_FLAG_DEFAULTS: dict[str, object]   # tên trường -> giá trị tắt
def ranking_config_hash(config: RetrievalConfig) -> str   # bỏ trường RT-1 đang bằng giá trị tắt
```

- [ ] **Step 1: Viết test fail**

```python
def test_default_hash_is_frozen():
    assert ranking_config_hash(RetrievalConfig()) == FROZEN   # hằng ở Global Constraints

@pytest.mark.parametrize("field,value", [("use_component_dependents", True), ("dependent_symbols_per_component", 5),
    ("may_call_factor", 0.5), ("use_trace_component", True), ("public_api_from_ports", True)])
def test_each_flag_changes_the_hash(field, value):
    assert ranking_config_hash(RetrievalConfig(**{field: value})) != FROZEN

@pytest.mark.parametrize("field,value", [("may_call_factor", -0.1), ("may_call_factor", 1.5),
    ("dependent_symbols_per_component", 0), ("dependent_symbols_per_component", True),
    ("use_trace_component", 1)])
def test_invalid_flag_values_are_rejected(field, value):
    with pytest.raises((InvalidQueryError, InvalidLimitError)):
        RetrievalConfig(**{field: value})
```

- [ ] **Step 2: Chạy, xác nhận fail.** `python -m pytest -q -p no:cacheprovider tests/test_retrieval_rt1.py` → FAIL (`unexpected keyword argument`).
- [ ] **Step 3: Cài đặt.** Thêm 5 trường cuối dataclass; `__post_init__` kiểm: `may_call_factor` số trong [0, 1]; `dependent_symbols_per_component` int không phải bool, ≥ 1; ba cờ còn lại là bool. `ranking_config_hash` mã hóa `asdict(config)` sau khi bỏ các khóa trong `RT1_FLAG_DEFAULTS` có giá trị đúng bằng giá trị tắt.
- [ ] **Step 4: Chạy lại** file test trên cùng `tests/test_graph_retrieval.py tests/test_run_graph_retrieval_config.py tests/test_dry_run.py` → PASS.
- [ ] **Step 5: Danh sách file cho người dùng commit:** `src/vgar/graph/retrieval.py tests/test_retrieval_rt1.py`.

### Task 2: `components_depending_on` (spec §4.1)

**Files:** Modify `src/vgar/graph/retrieval.py` (`_index_relations`, `retrieve`). Test `tests/test_retrieval_rt1.py`.

**Interfaces — Consumes:** Task 1. **Produces:** rationale `"COMPONENT_DEPENDENT"`; khi cờ bật và graph có Component, `"architecture_dependencies"` không còn trong `unavailable_features`.

Test dựng repo nhỏ trong `tmp_path` rồi `PythonGraphBuilder(repo_key="t/rt1", repository_revision="rev").build(root)` (builder tự dựng `G_arch`). Helper chung trong file test: `_retrieve(tmp_path, files: dict[str, str], *, anchor: str | None = None, issue: str = "", overlay: bool = False, include=None, **config) -> RetrievalResult`. Nó ghi `files`, build graph, tạo `GraphContextRetriever` với `count_tokens=lambda s: len(s) // 4`, `counter_label="test"`, `RetrievalConfig(**config)`. `anchor` là tên Function/Method, đổi thành node id; `overlay=True` dựng `TaskOverlayBuilder(document).build("t", issue, None)` và thêm anchor của overlay; gọi `retrieve(..., 12000, issue_text=issue, overlay=..., include=include)`. Thêm `_confidence(result, symbol) -> float` (confidence của ứng viên có `symbol` đó).

Repo mẫu `pricing_repo`: `shop/pricing/rounding.py` có `round_vnd`; `shop/checkout/total.py` có 4 hàm `subtotal`, `grand_total`, `apply_fee`, `split_bill`, mỗi hàm gọi `round_vnd` (`subtotal` gọi 2 lần); `shop/audit/log.py` có `record`, không ai import; mỗi thư mục có `__init__.py`; gốc không có `__init__.py`.

- [ ] **Step 1: Viết test fail**

```python
def test_dependents_add_at_most_three_callers(tmp_path):
    result = _retrieve(tmp_path, pricing_repo, anchor="round_vnd", use_component_dependents=True)
    added = [c for c in result.candidates if c["graph_rationale"][:1] == ["COMPONENT_DEPENDENT"]]
    assert [c["symbol"].rsplit(".", 1)[-1] for c in added][0] == "subtotal"      # 2 lời gọi đứng đầu
    assert len(added) == 3 and all(c["graph_distance"] == 2 for c in added)
    assert "architecture_dependencies" not in result.unavailable_features

def test_dependents_off_keeps_old_candidates(tmp_path):   # cờ tắt == RetrievalConfig()
def test_component_without_dependents_adds_nothing(tmp_path):   # anchor record trong audit
def test_cyclic_components_do_not_duplicate(tmp_path):   # a/core.py import b, b/core.py import a; mỗi node_id xuất hiện 1 lần
def test_flat_repo_without_components(tmp_path):   # một file utils.py ở gốc; không lỗi, "architecture_dependencies" vẫn unavailable
def test_dependents_respect_include(tmp_path):   # include loại checkout -> không có ứng viên COMPONENT_DEPENDENT
```

- [ ] **Step 2: Chạy, xác nhận fail** (không có ứng viên `COMPONENT_DEPENDENT`).
- [ ] **Step 3: Cài đặt** theo spec §4.1. Trong `_index_relations` dựng: `self._component_files: dict[str, set[str]]` (Component id → `properties.files`), `self._dependents: dict[str, set[str]]` (C → các D có `DEPENDS_ON` D → C), `self._component_calls: dict[tuple[str, str], Counter[str]]` ((D, C) → số cạnh `CALLS` từ symbol cha của CallSite trong D tới đích trong C; symbol cha lấy qua cạnh `CONTAINS` như `parents`, confidence là min của hai cạnh). Trong `retrieve`, sau `_walk`: với mỗi anchor, mỗi C chứa `path` của anchor, mỗi D trong `_dependents[C]` theo thứ tự id, lấy tối đa `dependent_symbols_per_component` symbol xếp theo (−số lời gọi, id), bỏ symbol đã có trong `states`, symbol không `_eligible`, symbol không qua `include`; thêm vào `states` dạng `(2, confidence, ("COMPONENT_DEPENDENT", f"DEPENDS_ON:{D}->{C}"))`. Ghi trace `retrieval_component_dependent`.
- [ ] **Step 4: Chạy** `tests/test_retrieval_rt1.py tests/test_graph_retrieval.py` → PASS.
- [ ] **Step 5: Danh sách file:** như Task 1.

### Task 3: `MAY_CALL` có giảm điểm (spec §4.2)

**Files:** Modify `src/vgar/graph/retrieval.py` (`_index_relations`). Test `tests/test_retrieval_rt1.py`.

Repo mẫu `dispatch_repo`: `store/cart.py`, `store/wishlist.py`, `store/inventory.py` mỗi file một class có method `add(self, item, qty)`; `store/service.py` có `handle_add(container, item, qty): container.add(item, qty)` và `checkout(cart): return apply_coupon(cart)`; `store/coupon.py` có `apply_coupon`. Builder static sinh 3 cạnh `MAY_CALL` (`candidate_count=3`).

- [ ] **Step 1: Viết test fail**

```python
def test_may_call_off_does_not_walk(tmp_path):        # anchor handle_add; không có ứng viên nào là ba method add qua cạnh CALLS
def test_may_call_factor_reaches_all_candidates(tmp_path):
    result = _retrieve(tmp_path, dispatch_repo, anchor="handle_add", may_call_factor=0.5)
    adds = {c["symbol"] for c in result.candidates if c["symbol"].endswith(".add")}
    assert adds == {"store.cart.Cart.add", "store.wishlist.Wishlist.add", "store.inventory.Inventory.add"}
    assert all(c["confidence"] <= 0.5 * 0.5 + 1e-9 for c in result.candidates if c["symbol"] in adds)
def test_higher_factor_never_lowers_score(tmp_path):   # điểm Cart.add ở 1.0 >= ở 0.5
def test_may_call_does_not_count_as_fan_in(tmp_path):  # public_api_risk của Cart.add giống khi cờ tắt
```

- [ ] **Step 2: Chạy, xác nhận fail.**
- [ ] **Step 3: Cài đặt.** Khi `may_call_factor > 0`, cạnh `MAY_CALL` đi qua cùng nhánh `CALLS` (nâng lên symbol cha của CallSite), confidence hiệu dụng `min(edge, parent) * may_call_factor`, nhãn `"CALLS"`/`"CALLERS"`, bỏ qua `min_edge_confidence` (thêm tham số `bypass_threshold: bool = False` cho `connect`), không thêm vào `self.callers`.
- [ ] **Step 4: Chạy** `tests/test_retrieval_rt1.py tests/test_graph_retrieval.py` → PASS.
- [ ] **Step 5: Danh sách file:** như Task 1.

### Task 4: Seed từ `TRACES_TO` (spec §4.3)

**Files:** Modify `src/vgar/graph/retrieval.py` (`retrieve`). Test `tests/test_retrieval_rt1.py`.

**Interfaces — Consumes:** `rank_component_traces(edges) -> list[dict]` từ `vgar.graph.trace_links`; overlay từ `TaskOverlayBuilder(document).build(task_id, issue_text, failing_tests)`. **Produces:** rationale `"TRACE_COMPONENT"`.

Repo mẫu `fee_repo`: `fees/discounts/rules.py`, `fees/shipping/rates.py`, `fees/tax/vat.py`, mỗi file có `calculate(order)` và một hàm public phụ (`discount_rate`, `weight_fee`, `weight_tax`); `fees/engine.py` có `total(order)` gọi cả ba. Issue có traceback:

```text
total() fails on an empty order
Traceback (most recent call last):
  File "fees/engine.py", line 6, in total
  File "fees/discounts/rules.py", line 2, in calculate
ZeroDivisionError: integer division or modulo by zero
```

- [ ] **Step 1: Viết test fail**

```python
def test_trace_component_ports_become_seeds(tmp_path):
    result = _retrieve(tmp_path, fee_repo, issue=TRACEBACK_ISSUE, overlay=True, use_trace_component=True)
    seeds = [c for c in result.candidates if c["graph_rationale"] == ["TRACE_COMPONENT"]]
    assert seeds and all(c["path"] == "fees/discounts/rules.py" for c in seeds)
    assert all(c["confidence"] == 0.45 for c in seeds)
def test_issue_without_traceback_is_unchanged(tmp_path):     # "free shipping is wrong at 500000": bật == tắt
def test_trace_below_threshold_is_ignored(tmp_path):         # sửa confidence TRACES_TO của overlay xuống 0.6 -> bật == tắt
def test_equal_traces_pick_the_same_component_every_run(tmp_path):   # 2 frame ở shipping và tax; 2 lần chạy cho cùng danh sách
def test_trace_seeds_respect_include(tmp_path):
```

- [ ] **Step 2: Chạy, xác nhận fail.**
- [ ] **Step 3: Cài đặt** trước `_walk`: nếu cờ bật và có overlay, lấy các cạnh `TRACES_TO` có `source_id` là Issue của overlay, `rank_component_traces`, lấy cạnh đầu nếu `confidence >= 0.7`. Symbol ứng viên: `properties.symbol_id` của các Port có `owner_component_id` là Component đó, chỉ node `_eligible` và qua `include`; xếp theo (−số từ chung giữa `_words(name)` và `task_words`, id); lấy tối đa `dependent_symbols_per_component`. Thêm vào `starts`, `scores[node] = max(scores.get(node, 0), 0.45)`, `seed_rationales[node] = ("TRACE_COMPONENT",)` nếu node không phải anchor. Ghi `trace_component_id` và `trace_seed_ids` vào `diagnostics`.
- [ ] **Step 4: Chạy** `tests/test_retrieval_rt1.py tests/test_graph_retrieval.py tests/test_trace_links.py` → PASS.
- [ ] **Step 5: Danh sách file:** như Task 1.

### Task 5: `public_api_risk` từ Port và tham số `config` của SQLite service (spec §4.6, §4.7)

**Files:** Modify `src/vgar/graph/retrieval.py`, `src/vgar/graph/sqlite_service.py:58-67`. Test `tests/test_retrieval_rt1.py`, `tests/test_sqlite_graph_service.py` (thêm test).

- [ ] **Step 1: Viết test fail**

```python
def test_public_api_uses_ports_when_present(tmp_path):
    # invoice/export.py: export_invoice (public), helper (public), _format_line (protected)
    result = _retrieve(tmp_path, invoice_repo, anchor="export_invoice", public_api_from_ports=True)
    risk = {c["symbol"].rsplit(".", 1)[-1]: c["features"]["public_api_risk"] for c in result.candidates}
    assert risk["_format_line"] == 0.0 and risk["export_invoice"] > 0.0
def test_public_api_falls_back_to_visibility_without_ports(tmp_path):   # xóa node Port khỏi document -> giống cờ tắt
def test_zero_weight_keeps_ranking(tmp_path):   # thứ tự node_id bật == tắt khi weights["public_api_risk"] == 0
def test_service_passes_config(tmp_path):   # get_related_context(..., config=RetrievalConfig(may_call_factor=0.5))
    # -> diagnostics["config"]["ranking_config_hash"] == ranking_config_hash(that config); bỏ config -> FROZEN
```

- [ ] **Step 2: Chạy, xác nhận fail.**
- [ ] **Step 3: Cài đặt.** `public_api_from_ports=True` và graph có node Port: `public = node_id in {Port.properties.symbol_id}`; không có Port thì dùng `visibility == "public"` như cũ. `SqliteGraphService.get_related_context(..., config: RetrievalConfig | None = None)` truyền `config` vào `GraphContextRetriever`; docstring có `Args`.
- [ ] **Step 4: Chạy** các file test trên cùng `tests/test_graph_retrieval.py` và các test MCP đang gọi `get_related_context` (`python -m pytest -q -p no:cacheprovider -k get_related_context`) → PASS.
- [ ] **Step 5: Danh sách file:** `src/vgar/graph/retrieval.py src/vgar/graph/sqlite_service.py tests/test_retrieval_rt1.py tests/test_sqlite_graph_service.py`.

### Task 6: Kiểm tra trên bộ 12 task tự tạo (spec §6 mục 1b)

**Files:** Create `scripts/check_rt1_benchmark.py`, `tests/test_check_rt1_benchmark.py`.

**Interfaces — Produces:** `check_benchmark(bundle: Path, configs: dict[str, RetrievalConfig]) -> dict` trả về, cho mỗi task và mỗi cấu hình: danh sách `node_id` theo thứ tự, hạng của file gold đầu tiên (`changed_source_files`), cờ `changed_vs_default`, cờ `repeatable` (chạy hai lần giống nhau). CLI: `python scripts/check_rt1_benchmark.py <bundle> --out <json>`; `<bundle>` là thư mục chứa `tasks/manifest.json` và 4 repo.

Cấu hình kiểm: `default`, mỗi cờ bật riêng (`may_call_factor=0.5`), và `all_on`. Task 06, 08, 09 (chờ sửa repo, traceback chưa đúng dạng) và task 03 (không còn cờ tương ứng, spec §6 mục 1b) chỉ kiểm `default` và `repeatable`; script đọc danh sách này từ hằng `DEFAULT_ONLY_TASKS = {"task-03": "no matching flag", "task-06": "pending repo fix", "task-08": "pending repo fix", "task-09": "pending repo fix"}` và ghi lý do.

- [ ] **Step 1: Viết test fail** trên một bundle 1 repo dựng trong `tmp_path` (một task, một repo git một commit): kết quả có đủ khóa; `default` có `repeatable=True`; task trong `DEFAULT_ONLY_TASKS` không có cấu hình khác `default`.
- [ ] **Step 2: Chạy, xác nhận fail.**
- [ ] **Step 3: Cài đặt.** Với mỗi task: `git -C <repo> checkout -q <base_commit>`, build graph, overlay từ `problem_statement` (không truyền `FAIL_TO_PASS`), `retrieve` với anchor từ overlay và `budget_tokens=12000`. Không sửa bundle (chỉ đọc; checkout đúng commit gốc đang có).
- [ ] **Step 4: Chạy test** → PASS. Chạy thật: `python scripts/check_rt1_benchmark.py C:/Users/nlhnh/Downloads/software_repair_benchmark/software_repair_benchmark --out %TEMP%/rt1_check/rt1_benchmark.json`. Expected: task 01 thay đổi khi bật `use_component_dependents`; task 02, 10, 11 không đổi; task 05 thay đổi khi bật `may_call_factor`; mọi task `repeatable`. Nếu khác, ghi Ruling và đưa vào báo cáo, không sửa bundle.
- [ ] **Step 5: Danh sách file:** `scripts/check_rt1_benchmark.py tests/test_check_rt1_benchmark.py`.

### Task 7: Manifest có gold và script đo cuốn chiếu (spec §5)

**Files:** Create `scripts/materialize_dev_gold.py`, `scripts/run_rt1_ablation.py`, `configs/rt1/*.json`, `tests/test_rt1_ablation.py`.

`configs/m1/w10_dev_manifest.json` không có `gold_patch_path`, `patch_hash`, `changed_source_files`, mà `run_graph_retrieval.evaluate_one` cần chúng. Pipeline đánh giá đọc mã nguồn từ archive `codeload.github.com` (`read_repository_sources`), không dùng checkout git; checkout trong WSL không được dùng.

**Interfaces — Produces:**

```python
# scripts/materialize_dev_gold.py
def materialize(manifest: Path, parquet: Path, root: Path) -> Path
# đọc parquet đã ghim, kiểm sha256 parquet == manifest["parquet_hash"] và query_hash từng task;
# ghi root/data/gold/patches/<id>.patch, chép parquet vào root/data/downloads/<dataset_revision>/,
# ghi root/data/manifests/w10-dev-50-gold.json: giữ mọi trường cũ, thêm patch_hash, gold_patch_path,
# changed_source_files, is_multi_file mỗi task và "source_manifest_hash" = manifest_hash gốc.

# scripts/run_rt1_ablation.py
# CLI: root manifest --config NAME=PATH (lặp; NAME "default" không cần PATH) --out DIR
#      [--only IDS_FILE] [--prune] [--resume] --budget-tokens 12000 --allow-fallback-counter|--tokenizer-manifest
```

`run_rt1_ablation.py` nạp `scripts/run_graph_retrieval.py` bằng `importlib` như `tests/test_run_graph_retrieval_config.py`. Với mỗi task: lần lượt mỗi cấu hình gọi `run_bounded_task` với `args` riêng (`retrieval_config` trỏ file của cấu hình, `cache_graphs=True`, `graph_cache_root=<out>/graphs`), nên graph chỉ build một lần. Mỗi cấu hình có một thư mục run riêng `<out>/<NAME>/` cùng định dạng `result.json` và `tasks/<id>.json` như `run_graph_retrieval.py`, để `compare_graph_runs` đọc được. `--prune`: sau task, xóa archive và file `.json` đi kèm trong `root/data/repositories/archives/`, cây trong `root/data/repositories/trees/` và graph của task trong `<out>/graphs/`. `--resume`: bỏ qua task đã có `tasks/<id>.json` ở mọi cấu hình.

File cấu hình: `configs/rt1/dependents.json`, `may_call_0_5.json`, `may_call_1_0.json`, `trace.json`, mỗi file chỉ đặt một cờ (spec §5 đo các cờ §4.1–4.3; `public_api_from_ports` có trọng số 0 nên không đổi thứ hạng, không cần đo).

- [ ] **Step 1: Viết test fail**: `materialize` trên parquet giả 2 dòng ghi đúng 4 trường mới, từ chối parquet sai hash và `query_hash` sai; `run_rt1_ablation` với `run_bounded_task` được thay bằng hàm giả: mỗi cấu hình có thư mục riêng, `--resume` không gọi lại task đã có kết quả, `--prune` chỉ xóa file của task vừa xong (tạo sẵn file của task khác, kiểm còn nguyên).
- [ ] **Step 2: Chạy, xác nhận fail.**
- [ ] **Step 3: Cài đặt** hai script; docstring có `Args`.
- [ ] **Step 4: Chạy** `tests/test_rt1_ablation.py tests/test_run_graph_retrieval_config.py` → PASS.
- [ ] **Step 5: Danh sách file:** hai script, `configs/rt1/`, `tests/test_rt1_ablation.py`.

### Task 8: Đo, chốt `RT1_CONFIG`, báo cáo

**Files:** Modify `src/vgar/graph/retrieval.py` (thêm `RT1_CONFIG`), `tests/test_retrieval_rt1.py`, spec §5 (ghi kết quả). Create `configs/rt1/rt1_config.json`, `docs/status/tv2_rt_1_retrieval_run_2026-11-XX.md`.

Chạy trong WSL, gốc dữ liệu `~/rt1` (tạo mới), parquet `~/w9/dataset/test-00000-of-00001.parquet`.

- [ ] **Step 1: Gold.** `python scripts/materialize_dev_gold.py configs/m1/w10_dev_manifest.json ~/w9/dataset/test-00000-of-00001.parquet ~/rt1`. Expected: 50 task, `source_manifest_hash` khớp.
- [ ] **Step 2: Chạy thử 3 task** ([test] mục 3, tầng 2): `run_rt1_ablation.py` với `--only` gồm 3 task đầu của danh sách 25 task ở Step 3, `default` và cả 4 file cấu hình, `--prune`, thư mục `--out ~/rt1/results/dryrun`. Expected: 3 task SUCCEEDED ở mọi cấu hình, thư mục archive và tree rỗng sau khi chạy. Lỗi thì sửa trước khi chạy tiếp.
- [ ] **Step 3: Bước 1, chỉnh tham số trên 25 task đã đo ở TR-1.** File `--only` gồm các task của manifest có thư mục trong `~/tr1-repos` (spec §5 bước 1; chỉ dùng danh sách tên, pipeline tải archive). Chạy `run_rt1_ablation.py` với `default` và cả 4 file cấu hình, `--prune`. So từng cấu hình với `default` bằng `compare_graph_runs` (arm `graph`; `file_recall@5`, phụ `function_recall@5`, `file_mrr`, `packed_gold_function_in_context`). Chọn: cờ vào `RT1_CONFIG` khi `mean_delta` của `file_recall@5` hoặc `function_recall@5` > 0 và MRR không giảm có ý nghĩa, tức cận trên CI95 của delta `file_mrr` ≥ 0 (spec §5); với `may_call_factor`, chọn mức tốt hơn trong hai mức đã thử. Ghi lựa chọn vào `configs/rt1/rt1_config.json`.
- [ ] **Step 4: Bước 2, số liệu trên đủ 50 task.** Chạy `default`, từng cờ đã chọn, và `rt1_config` với `--prune --resume`. Ghi dung lượng đĩa lớn nhất (`du -sh ~/rt1` sau mỗi task, lấy max). So `rt1_config` và từng cờ với `default` bằng `compare_graph_runs`. Không chạy BM25 hay baseline khác: R1 dùng lại các run này (spec §5).
- [ ] **Step 5: Thêm `RT1_CONFIG`** vào `retrieval.py` đúng giá trị trong `configs/rt1/rt1_config.json`; test `test_rt1_config_matches_the_measured_file` đọc file JSON và so với `RT1_CONFIG`; test default hash vẫn bằng hằng cũ.
- [ ] **Step 6: Báo cáo** `docs/status/tv2_rt_1_retrieval_run_2026-11-XX.md`: kết quả chạy thử 3 task; bảng từng cờ (25 task, ghi rõ "25/50", chỉ dùng để chọn); bảng 50 task (Recall@5 file và hàm, MRR, Recall@B ở 12.000 token tức `packed_gold_file_in_context` và `packed_gold_function_in_context`, so với `default`, kèm CI95); bảng riêng các task có traceback đường dẫn tuyệt đối (task có `File "/` trong `problem_statement`); kết quả Task 6; dung lượng đĩa lớn nhất; `recent_change_frequency` unavailable; hai giới hạn ở spec §5 (manifest `min1`, 5/50 task nhiều file theo gold; repo mẫu chung chưa chốt); đường dẫn các run để R1 dùng lại; mỗi số kèm lệnh tái tạo.
- [ ] **Step 7: Toàn bộ suite.** Windows: `python -m pytest -q -p no:cacheprovider -m "not hf and not docker"` → chỉ còn 3 test fail đã biết (`tests/m2/w910/test_runner_contract.py::test_different_arm_contexts_can_share_template_without_same_prompt`, `tests/test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory`, `tests/test_w9_bundle.py::test_checked_in_fixture_validates_and_matches_recipe`). WSL: `tests/test_retrieval_rt1.py tests/test_graph_retrieval.py tests/test_rt1_ablation.py tests/test_check_rt1_benchmark.py` → PASS.
- [ ] **Step 8: Danh sách file cho người dùng commit** và lệnh commit kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
