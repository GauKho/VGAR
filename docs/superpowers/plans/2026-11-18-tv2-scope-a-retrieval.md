# Phạm vi A cho retrieval (TV2, R1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm bốn trường mới (mặc định tắt) vào `RetrievalConfig` — hạ trần hạt giống, mở rộng hàm theo file, đóng gói khung xương, dừng sớm — cùng `SERVED_CONFIG` cho MCP server, rồi chỉnh trên `tune25` để chọn cánh `task_trace_a`.

**Architecture:** Mọi thay đổi xếp hạng và đóng gói nằm trong `GraphContextRetriever.retrieve()` (`src/vgar/graph/retrieval.py`), bật bằng trường của `RetrievalConfig`. Giá trị tắt của trường mới vào `RT1_FLAG_DEFAULTS` để hash cũ không đổi. MCP server lấy cấu hình từ hằng `SERVED_CONFIG`, giữ bằng `RetrievalConfig()` trong phạm vi này.

**Tech Stack:** Python 3.11, `ast`, pytest/unittest; bộ đo R1 trong `ablation_matrix/`.

**Spec:** `docs/superpowers/specs/2026-11-18-tv2-scope-a-retrieval-design.md`

## Global Constraints

- `ranking_config_hash(RetrievalConfig())` giữ nguyên giá trị đóng băng trong `tests/test_graph_retrieval.py` (`FROZEN_RANKING_HASH`).
- `ranking_config_hash(RT1_CONFIG)` = `sha256:d3e6933772781ab664efdad583d308874a07fc9106c82fa89796886065137712` (ghi trong `docs/protocol_freeze_r1_heldout.md`).
- Mặc định của trường mới: `anchor_seed_limit=0`, `file_expansion=0`, `skeleton_packing=False`, `pack_stop_ratio=0.0`; cả bốn có trong `RT1_FLAG_DEFAULTS`.
- `SERVED_CONFIG == RetrievalConfig()` trong phạm vi này.
- `ContextPayload` không thêm/bớt trường; thông tin mới chỉ vào `RetrievalResult` và `diagnostics`.
- Không chạy đo khi G1 đang chạy; không dùng `--prune` khi chỉnh (lỗi E10).
- Người dùng tự commit; executor chỉ liệt kê file thay đổi.

## Review Focus

1. **Agent gọi `get_related_context` không có `issue_text`** → vẫn trả context, không lỗi, không mất anchor; `file_expansion` không thêm nút. Test ở Task 5.
2. **Class được đóng gói khung xương trước method gold bên trong nó** → thân method vẫn vào gói khi còn ngân sách. Test ở Task 4.
3. **File anchor rất lớn (hàng trăm hàm)** → mở rộng không vượt `file_expansion` và danh sách ứng viên không vượt `max_candidates`. Test ở Task 3.
4. **Đoạn mã không parse được khi dựng khung xương** (ví dụ cú pháp Python cũ) → giữ nguyên đoạn mã gốc, không lỗi. Test ở Task 4.
5. **`pack_stop_ratio` cắt mất phần đặt chỗ cho dependency** → dừng sớm không áp dụng cho mục đặt chỗ (`reserved_reference`). Test ở Task 4.

---

### Task 1: Trường cấu hình mới, giữ hash, và `SERVED_CONFIG`

**Files:**
- Modify: `src/vgar/graph/retrieval.py` (`RetrievalConfig` ~36-103, `RT1_FLAG_DEFAULTS` ~95-101)
- Test: `tests/test_graph_retrieval.py`

**Interfaces:**
- Produces: `RetrievalConfig.anchor_seed_limit: int = 0`, `.file_expansion: int = 0`, `.skeleton_packing: bool = False`, `.pack_stop_ratio: float = 0.0`; hằng `SERVED_CONFIG: RetrievalConfig` trong `vgar.graph.retrieval`.

- [ ] **Step 1: Viết test thất bại**

```python
def test_rt1_and_served_config_hashes_unchanged(self) -> None:
    from vgar.graph.retrieval import RT1_CONFIG, SERVED_CONFIG
    self.assertEqual(ranking_config_hash(RT1_CONFIG),
                     "sha256:d3e6933772781ab664efdad583d308874a07fc9106c82fa89796886065137712")
    self.assertEqual(SERVED_CONFIG, RetrievalConfig())
    self.assertEqual(ranking_config_hash(RetrievalConfig(anchor_seed_limit=0, file_expansion=0,
                     skeleton_packing=False, pack_stop_ratio=0.0)), FROZEN_RANKING_HASH)

def test_scope_a_fields_are_validated(self) -> None:
    for bad in ({"anchor_seed_limit": -1}, {"file_expansion": True}, {"skeleton_packing": 1},
                {"pack_stop_ratio": 1.0}, {"pack_stop_ratio": -0.1}):
        with self.assertRaises((InvalidLimitError, InvalidQueryError)):
            RetrievalConfig(**bad)
```

- [ ] **Step 2: Chạy, xác nhận thất bại**

Run: `.venv/Scripts/python.exe -m pytest tests/test_graph_retrieval.py -k "served_config or scope_a_fields" -q`
Expected: FAIL (`SERVED_CONFIG` chưa có / trường lạ).

- [ ] **Step 3: Cài**

Thêm bốn trường vào `RetrievalConfig`, kiểm tra trong `__post_init__` (int ≥ 0 không phải bool; bool; `0 <= pack_stop_ratio < 1`), thêm bốn giá trị tắt vào `RT1_FLAG_DEFAULTS`, thêm `SERVED_CONFIG = RetrievalConfig()` cạnh `RT1_CONFIG`.

- [ ] **Step 4: Chạy lại**

Run: `.venv/Scripts/python.exe -m pytest tests/test_graph_retrieval.py -q`
Expected: tất cả PASS (gồm `test_frozen_ranking_config_hash`).

---

### Task 2: Hạ trần hạt giống (`anchor_seed_limit`)

**Files:**
- Modify: `src/vgar/graph/retrieval.py` (`_anchor_seed_limit` ~670, `component_limit` ~251)
- Test: `tests/test_graph_retrieval.py`

**Interfaces:**
- Consumes: `RetrievalConfig.anchor_seed_limit` (Task 1).
- Produces: `_anchor_seed_limit()` trả `anchor_seed_limit` khi > 0; hàm mới `_default_seed_limit()` trả giá trị cũ (`max_candidates // 2` nếu `max_hops`, ngược lại `max_candidates`), dùng cho `component_limit`.

- [ ] **Step 1: Viết test thất bại**

```python
def test_anchor_seed_limit_caps_walk_seeds(self) -> None:
    anchors = [self.node_id("login"), self.node_id("create_user_service")]
    base = self.retriever().retrieve(anchors, 1000, issue_text="login fails")
    capped = self.retriever(config=RetrievalConfig(anchor_seed_limit=1)).retrieve(
        anchors, 1000, issue_text="login fails")
    seeds = lambda result: {c["node_id"] for c in result.candidates if c["graph_distance"] == 0}
    self.assertEqual(len(seeds(base)), 2)
    self.assertEqual(seeds(capped), {self.node_id("login")})   # higher priority: matches the issue

def test_anchor_seed_limit_keeps_component_limit(self) -> None:
    retriever = self.retriever(config=RetrievalConfig(anchor_seed_limit=1))
    self.assertEqual(retriever._default_seed_limit(), RetrievalConfig().max_candidates // 2)
```

- [ ] **Step 2: Chạy, xác nhận thất bại**

Run: `.venv/Scripts/python.exe -m pytest tests/test_graph_retrieval.py -k anchor_seed_limit -q`
Expected: FAIL.

- [ ] **Step 3: Cài** `_default_seed_limit(self) -> int` (thân hiện tại của `_anchor_seed_limit`); `_anchor_seed_limit` trả `self.config.anchor_seed_limit or self._default_seed_limit()`; dòng `component_limit` dùng `_default_seed_limit()`.

- [ ] **Step 4: Chạy lại** `tests/test_graph_retrieval.py` → PASS.

---

### Task 3: Mở rộng hàm theo file, xếp lại theo thân hàm (`file_expansion`)

**Files:**
- Modify: `src/vgar/graph/retrieval.py` (`__init__` thêm chỉ mục; `retrieve()` sau `_walk`/dependents ~281-291; sau `candidates.sort` ~336)
- Test: `tests/test_graph_retrieval.py`

**Interfaces:**
- Consumes: `RetrievalConfig.file_expansion` (Task 1); `self._source_evidence.similarity(node_id, task_words)` (có sẵn).
- Produces: nút mở rộng trong `states` với `(1, 0.85 * anchor_score, ("FILE_EXPANSION",))`; ứng viên có `graph_rationale == ["FILE_EXPANSION"]`.

Repo tạm cho test (viết trong test, `tempfile.TemporaryDirectory`), file `pkg/codec.py`:

```python
class Codec:
    def parse(self, raw):
        return raw.split(",")

    def checksum(self, raw):
        total = 0
        for byte in raw.encode():
            total = (total + byte) % 255
        return total

    def unrelated(self):
        return 1
```

- [ ] **Step 1: Viết test thất bại**

```python
def test_file_expansion_adds_same_file_method_by_body_similarity(self) -> None:
    graph, root = self.codec_repo()          # builds pkg/codec.py above with PythonGraphBuilder
    anchor = self.node_id("parse", "Method", graph)
    issue = "Codec.parse is fine but the checksum total is wrong for some byte values"
    plain = self.retriever(graph, root).retrieve([anchor], 2000, issue_text=issue)
    wide = self.retriever(graph, root, config=RetrievalConfig(file_expansion=5)).retrieve(
        [anchor], 2000, issue_text=issue)
    checksum, unrelated = self.node_id("checksum", "Method", graph), self.node_id("unrelated", "Method", graph)
    self.assertNotIn(checksum, {c["node_id"] for c in plain.candidates})
    expanded = {c["node_id"]: c for c in wide.candidates}
    self.assertEqual(expanded[checksum]["graph_rationale"], ["FILE_EXPANSION"])
    self.assertNotIn(unrelated, expanded)          # body similarity 0: not added

def test_file_expansion_respects_max_candidates(self) -> None:
    config = RetrievalConfig(file_expansion=50, max_candidates=3)
    result = self.retriever(config=config).retrieve([self.node_id("find_user", "Method")], 2000,
                                                    issue_text="find_user normalize user service")
    self.assertLessEqual(len(result.candidates), 3)
```

- [ ] **Step 2: Chạy, xác nhận thất bại**

Run: `.venv/Scripts/python.exe -m pytest tests/test_graph_retrieval.py -k file_expansion -q`
Expected: FAIL.

- [ ] **Step 3: Cài**

- `__init__`: `self._functions_by_path: dict[str, list[str]]` cho nút `Function`/`Method` có `path`.
- Trong `retrieve()`, khi `file_expansion > 0`, có `task_words` và `self._source_evidence`: file = `path` của các nút trong `states` có `distance == 0` và thuộc `anchors`; điểm file = max `scores.get(anchor, 1.0)` của anchor trong file; ứng viên = hàm của các file đó, chưa có trong `states`, qua `include` và không bắt đầu bằng `tests.`, độ giống > 0; sắp `(-similarity, node_id)`; giữ `file_expansion` nút đầu cho cả task; thêm vào `states`.
- Sau `candidates.sort(...)`: nếu `file_expansion > 0` thì `candidates = candidates[:self.config.max_candidates]`.
- Thêm helper test `codec_repo()` trong `GraphRetrievalTests` (dựng graph từ thư mục tạm, giữ thư mục sống tới hết test bằng `self.addCleanup`).

- [ ] **Step 4: Chạy lại** `tests/test_graph_retrieval.py` → PASS.

---

### Task 4: Đóng gói khung xương, luật chồng lấn mới, dừng sớm

**Files:**
- Modify: `src/vgar/graph/retrieval.py` (vòng đóng gói ~344-400; `RetrievalResult` ~120; hàm mới `_skeleton`)
- Modify: `src/vgar/graph/sqlite_service.py` (~133-138, thêm `diagnostics["skeleton_items"]`)
- Test: `tests/test_graph_retrieval.py`, `tests/test_sqlite_graph_service.py`

**Interfaces:**
- Consumes: `skeleton_packing`, `pack_stop_ratio` (Task 1).
- Produces: `_skeleton(snippet: str) -> str` (module-level); `RetrievalResult.skeleton_items: list[str] = field(default_factory=list)` (trường cuối, có mặc định để các chỗ dựng cũ không hỏng); omission reason `"score_below_stop_ratio"`; `diagnostics["skeleton_items"]` trong kết quả `SQLiteGraphService.get_related_context`.

- [ ] **Step 1: Viết test thất bại**

```python
def test_skeleton_keeps_signatures_drops_bodies(self) -> None:
    from vgar.graph.retrieval import _skeleton
    source = "class A(B):\n    def f(self, x):\n        return x + 1\n\n    def g(self):\n        pass\n"
    text = _skeleton(source)
    self.assertIn("class A(B):", text); self.assertIn("def f(self, x):", text); self.assertNotIn("return x + 1", text)
    self.assertEqual(_skeleton("def broken(:\n    pass\n"), "def broken(:\n    pass\n")   # unparsable: unchanged

def test_skeleton_packing_keeps_inner_method_body(self) -> None:
    anchors = [self.node_id("UserService", "Class"), self.node_id("find_user", "Method")]
    result = self.retriever(config=RetrievalConfig(skeleton_packing=True)).retrieve(
        anchors, 2000, issue_text="UserService find_user")
    items = {item.node_id: item for item in result.context.items}
    cls, method = self.node_id("UserService", "Class"), self.node_id("find_user", "Method")
    self.assertIn(cls, result.skeleton_items)
    self.assertNotIn("return self.normalize(name)", items[cls].snippet)
    self.assertIn("return self.normalize(name)", items[method].snippet)

def test_pack_stop_ratio_drops_low_scores(self) -> None:
    result = self.retriever(config=RetrievalConfig(pack_stop_ratio=0.5)).retrieve(
        [self.node_id("login")], 5000, issue_text="login fails")
    top = result.candidates[0]["relevance_score"]
    for item in result.context.items:
        self.assertGreaterEqual(item.relevance_score, 0.5 * top)
    self.assertTrue(any(o["reason"] == "score_below_stop_ratio" for o in result.omissions)
                    or all(c["relevance_score"] >= 0.5 * top for c in result.candidates))
```

Test cho Review Focus 5: với một anchor có dependency được đặt chỗ (sự kiện trace `context_reference_selected` khi
`pack_stop_ratio=0`), chạy lại với `pack_stop_ratio=0.99` — mọi node từng được đặt chỗ vẫn có trong `context.items`.

Trong `tests/test_sqlite_graph_service.py`: một test gọi `self.service.get_related_context(..., config=RetrievalConfig(skeleton_packing=True))` và khẳng định `"skeleton_items" in result["diagnostics"]`.

- [ ] **Step 2: Chạy, xác nhận thất bại**

Run: `.venv/Scripts/python.exe -m pytest tests/test_graph_retrieval.py tests/test_sqlite_graph_service.py -k "skeleton or stop_ratio" -q`
Expected: FAIL.

- [ ] **Step 3: Cài**

- `_skeleton`: `ast.parse(textwrap.dedent(snippet))`; giữ dòng import, dòng khai báo class (kèm decorator), dòng đầu tới hết chữ ký mỗi `def` thêm ` ...`; lỗi parse thì trả nguyên `snippet`.
- Vòng đóng gói: với `skeleton_packing` và loại nút `Class`/`File`/`Module`, `snippet = _skeleton(snippet)`, ghi node vào `skeleton_ids`. Hai danh sách vùng: `full_ranges` chỉ chặn mục thân đầy đủ, `skeleton_ranges` chỉ chặn mục khung xương; giữ hành vi cũ khi tắt cờ.
- Dừng sớm: `top = candidates[0]["relevance_score"]` (nếu có); trong vòng lặp, mục **không** phải `reserved_reference` có điểm `< pack_stop_ratio * top` thì ghi omission `"score_below_stop_ratio"` và bỏ qua.
- `RetrievalResult(..., skeleton_items=sorted(skeleton_ids))`; `sqlite_service` thêm `"skeleton_items": result.skeleton_items` vào `diagnostics`.

- [ ] **Step 4: Chạy lại** `tests/test_graph_retrieval.py tests/test_sqlite_graph_service.py` → PASS.

---

### Task 5: MCP server dùng `SERVED_CONFIG`

**Files:**
- Modify: `src/vgar/mcp/servers/graph_server.py` (~228, truyền `config=SERVED_CONFIG`)
- Test: `tests/mcp_server/test_tv2_context_budget.py` (dùng fixture `big_server` có sẵn)

**Interfaces:**
- Consumes: `SERVED_CONFIG` (Task 1), `diagnostics["skeleton_items"]` (Task 4).

- [ ] **Step 1: Viết test thất bại**

```python
def test_served_config_reaches_the_service(big_server, monkeypatch):
    seen = {}
    original = graph_server.graph_service.get_related_context
    def spy(*args, **kwargs):
        seen["config"] = kwargs.get("config")
        return original(*args, **kwargs)
    monkeypatch.setattr(graph_server.graph_service, "get_related_context", spy)
    anchors, version = big_server
    graph_server.get_related_context(anchors, graph_version=version, task_id="t")
    from vgar.graph.retrieval import SERVED_CONFIG
    assert seen["config"] == SERVED_CONFIG

def test_empty_issue_text_still_returns_context_with_scope_a_flags(big_server, monkeypatch):
    from vgar.graph import retrieval
    monkeypatch.setattr(graph_server, "SERVED_CONFIG", retrieval.RetrievalConfig(
        anchor_seed_limit=5, file_expansion=10, skeleton_packing=True, pack_stop_ratio=0.3))
    anchors, version = big_server
    result = graph_server.get_related_context(anchors, graph_version=version, task_id="t", issue_text="")
    assert result["status"] == "ok" and result["data"]["context"]["items"]
    assert "skeleton_items" in result["data"]["diagnostics"]
```

(Đọc fixture `big_server` trong file để dùng đúng giá trị nó trả về; chỉnh phần giải nén `anchors, version` cho khớp.)

- [ ] **Step 2: Chạy, xác nhận thất bại**

Run: `.venv/Scripts/python.exe -m pytest tests/mcp_server/test_tv2_context_budget.py -k "served_config or empty_issue" -q`
Expected: FAIL.

- [ ] **Step 3: Cài** `from vgar.graph.retrieval import SERVED_CONFIG` ở đầu `graph_server.py`; truyền `config=SERVED_CONFIG` trong lời gọi service.

- [ ] **Step 4: Chạy lại** `tests/mcp_server` → PASS.

---

### Task 6: Cánh chỉnh tham số, so sánh trong cùng lượt, sửa nhãn tài liệu

**Files:**
- Modify: `ablation_matrix/retrieval_variants.py` (`GRAPH_ARM_SPECS`)
- Modify: `ablation_matrix/compare_runs.py` (thêm so sánh giữa các cánh trong cùng một lượt)
- Modify: `ablation_matrix/run_r1_ablation.py` (chú thích `PRIMARY_PAIRS`)
- Modify (nhãn): `docs/status/tv2_r1_scip_2026-11-18.md`, `docs/status/tv2_open_issues_2026-11-18.md`
- Test: `ablation_matrix/tests/test_compare_runs.py`, `ablation_matrix/tests/test_retrieval_variants.py`

**Interfaces:**
- Produces: cánh `a_seed10`, `a_seed20`, `a_seed30` = `("overlay", {"may_call_factor": 0.5, "anchor_seed_limit": k}, False)`; `compare_runs.compare_arms(run: dict[str, dict], base_arm: str, arms: list[str]) -> dict` cùng định dạng `pairs` như `compare()`; CLI `compare_runs.py <results> <run> --arms-vs task_trace_rt1`.

- [ ] **Step 1: Viết test thất bại**

```python
def test_compare_arms_within_one_run():
    run = {"a": {"arms": {"task_trace_rt1": {"metrics": {"function_recall@5": 0.0}},
                          "a_seed20": {"metrics": {"function_recall@5": 1.0}}}, "graph": {"build_seconds": 1.0}}}
    out = compare_runs.compare_arms(run, "task_trace_rt1", ["a_seed20"])
    assert out["pairs"]["a_seed20"]["function_recall@5"]["delta"] == 1.0
```

và trong `test_retrieval_variants.py`: `a_seed20` có trong `GRAPH_ARMS` với cờ `anchor_seed_limit == 20`.

- [ ] **Step 2: Chạy, xác nhận thất bại**: `.venv/Scripts/python.exe -m pytest ablation_matrix/tests -q` → FAIL.

- [ ] **Step 3: Cài** ba cánh, `compare_arms` (dùng lại `ci95`, `METRICS`), cờ CLI `--arms-vs BASE_ARM`. Đổi chú thích `PRIMARY_PAIRS` và các dòng tài liệu: `task_trace_rt1` là "ứng viên RT-1"; server hiện chạy cấu hình tương đương `task_trace`.

- [ ] **Step 4: Chạy lại** `ablation_matrix/tests` → PASS.

---

### Task 7: Chỉnh trên `tune25`, chọn và kiểm chứng `task_trace_a` (chạy sau khi G1 xong)

Không viết code mới; chỉ cấu hình cánh và chạy đo.

- [ ] **Step 1: Lượt 1 (hạ trần)**

```bash
cd /mnt/d/kltn/vgar_mcp_mvp_demo && PYTHONPATH=src ~/.vgar-wsl/bin/python ablation_matrix/run_r1_ablation.py \
  ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json --out ~/rt1/results/scope_a_tune25_seed \
  --allow-fallback-counter --only ~/rt1/tune25.txt 2>&1 | tee ~/rt1/scope_a_tune25_seed.log
python3 ablation_matrix/compare_runs.py ~/rt1/results scope_a_tune25_seed --arms-vs task_trace_rt1
```
Chọn theo luật mục 4 của spec (R@5 hàm, rồi reach hàm, rồi giá trị nhỏ hơn).

- [ ] **Step 2: Lượt 2 (mở rộng + đóng gói):** thêm cánh `a_e20/a_e50/a_e100` (trần đã chọn + `file_expansion`), rồi `a_pack0/a_pack3/a_pack5` (e đã chọn + `skeleton_packing=True` + `pack_stop_ratio` 0 / 0,3 / 0,5); chạy như Step 1 ra `scope_a_tune25_more`; chọn theo luật mục 4.

- [ ] **Step 3: Chốt `task_trace_a`** trong `GRAPH_ARM_SPECS` với giá trị đã chọn; thêm cặp `task_trace_a − task_trace_rt1`, `task_trace_a − task_trace` vào `PAIRS`; chạy `ablation_matrix/tests`.

- [ ] **Step 4: Kiểm chứng** trên 25 task còn lại (`comm -23 <(sort ~/rt1/all50.txt) <(sort ~/rt1/tune25.txt) > ~/rt1/val25.txt`), ra `scope_a_val25`; so với tiêu chí ghi trước ở mục 4 của spec; viết `docs/status/tv2_scope_a_dev_2026-11-<ngày>.md`.

- [ ] **Step 5: Gửi luồng B** tên cánh, cờ, `ranking_config_hash(task_trace_a config)`, kết quả so với tiêu chí (điểm đồng bộ S2).

---

## Sau mỗi task

Liệt kê file đã đổi để người dùng commit. Chạy `ruff check` trên file đã sửa (chỉ báo lỗi mới, không sửa lỗi có sẵn).
