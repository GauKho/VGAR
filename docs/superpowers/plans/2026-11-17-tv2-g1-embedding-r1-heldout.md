# TV2 · Chốt G1, baseline embedding, R1 trên held-out — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đóng G1 (Graph quality) với đủ 5 metric của proposal, thêm baseline embedding và `dependency_frontier_recall@B` vào R1, rồi chuẩn bị và chạy R1 trên held-out đúng một lần sau freeze.

**Architecture:** G1 chỉ thêm khả năng chấm một sheet đối chiếu thứ hai (của người) và một bộ nhãn ranh giới Component; số G1 cũ giữ nguyên. R1 thêm một cánh văn bản `embedding` cùng giao diện `RankRecord` với BM25, một metric packed `frontier_in_context` tính trên `gold["frontier_functions"]`, và RRF tính lại trong `summarize` từ danh sách top-100 đã lưu. Cổng held-out được tham số hóa theo protocol để R1 có file freeze và tag riêng.

**Tech Stack:** Python 3.11, pytest, `sentence-transformers` + `torch` (chỉ trong `~/.vgar-wsl`, không vào CI), WSL cho mọi lượt chạy thật.

**Spec:** `docs/superpowers/specs/2026-11-17-tv2-g1-embedding-r1-heldout-design.md`

## Global Constraints

- Plan dùng **đề xuất** của spec cho các quyết định D1-1…D3-3, D2-4. Task phụ thuộc quyết định ghi ở dòng **Điều kiện**; quyết định khác đề xuất thì bỏ hoặc sửa task đó.
- Người dùng tự commit (không `git commit` / `git push`). Bước cuối của mỗi task là **liệt kê file để người dùng commit**.
- Lượt chạy có model (GPU) và lượt held-out do **người dùng chạy**; Claude viết code, test và lệnh.
- Ngân sách context 12.000 token; bộ đếm `utf8_bytes_ceil_div4` (cờ `--allow-fallback-counter`).
- Bootstrap ghép cặp 2.000 lần, seed 0, CI95 (hàm `_bootstrap` có sẵn).
- RRF: k = 60, trọng số 1, trộn riêng danh sách file và danh sách hàm từ top-100 mục đã lưu (`ranked`); báo cáo gọi là **phân tích thêm ngoài proposal**.
- Model embedding: `nomic-ai/CodeRankEmbed`, ghim revision SHA; tiền tố truy vấn đúng nguyên văn `Represent this query for searching relevant code: `; dự phòng `jinaai/jina-embeddings-v2-base-code`.
- Báo cáo G1 luôn ghi "nhãn do Claude gán"; độ khớp của lượt Claude thứ hai gọi là "độ nhất quán của Claude", chỉ lượt người mới gọi là "độ khớp với người".
- `F*_approx` gọi là "xấp xỉ của `F*`", không gọi là `F*`.
- Chạy test Windows: `PYTHONPATH=src D:/kltn/vgar_mcp_mvp_demo/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider <test>`; WSL: `PYTHONPATH=<repo>/src ~/.vgar-wsl/bin/python`.
- Không đổi số của các lượt R1 đã có: cánh và metric mới chỉ xuất hiện khi bật cờ hoặc khi `gold` có khóa mới.

## Review Focus

- Task có patch gold không thêm dòng nào nhắc tên định nghĩa trong repo: `frontier_functions` phải bằng đúng `gold_functions`, không rỗng hơn. → test ở Task 4.
- Tên ngắn trùng nhiều định nghĩa (ví dụ `__init__`, `get`): không được đưa vào `F*_approx`. → test ở Task 4.
- Cache embedding bị dùng chéo giữa hai model hoặc hai revision: khóa cache phải gồm model id và revision. → test ở Task 5.
- Lượt R1 cũ (không có cờ embedding) chạy `summarize` với bản code mới: không được lỗi, không được thêm cặp rỗng làm hỏng bảng. → test ở Task 6.
- Tag `protocol-freeze-r1` không được mở khóa held-out của repair, và ngược lại. → test ở Task 7.

---

### Task 1: Đưa báo cáo G1 vào repo, ghép 5 metric, đối chiếu §8.3

**Files:**
- Create: `docs/status/tv2_g1_graph_quality_2026-11-17.md`

**Interfaces:**
- Consumes: `~/rt1/g1/report/g1_report.md`, `g1_report.json` (WSL); `docs/status/tv2_tr_1_trace_links_run_2026-11-10.md`; `docs/status/tv2_u1_incremental_2026-11-11.md`.
- Produces: bảng 5 metric G1 mà Task 9 (file freeze) và báo cáo R1 trích dẫn.

- [ ] **Step 1: Đọc `g1_report.json` trong WSL và chép nguyên số** (P, R, CI95, n, tp, fp, fn cho `static`, `tsg`, `tsg_jarvis`; độ khớp 0,967, kappa 1,000; mục chốt C017).
- [ ] **Step 2: Viết báo cáo** với các mục: Ai gán nhãn (đúng câu của Global Constraints); bảng 5 metric của [P] dòng 1341–1347 (symbol P/R và call edge P/R từ G1; trace link P/R từ TR-1: top-1 P 0,70 / R 0,50, ngưỡng ≥ 0,7 P 0,45 / R 0,58; incremental correctness từ U1: 12/12; component boundary: "chưa đo, xem Task 3"); mục §8.3 ghi số `CALLS` và `CALLS + MAY_CALL` của cấu hình phục vụ (tsg, JARVIS tắt mặc định) và câu "proposal không đặt ngưỡng; nhóm kết luận"; mục giới hạn (lỗi bộ công cụ đã biết: tham số lambda, `examples/` của matplotlib, bí danh module; JARVIS lỗi/timeout ở `eval.log`; `scip_tsg` không chạy theo D1-3).
- [ ] **Step 3: Kiểm tra** mọi số trong báo cáo khớp `g1_report.json` (đối chiếu từng dòng bằng mắt, ghi "đã đối chiếu" vào cuối báo cáo).
- [ ] **Step 4: Liệt kê file để người dùng commit:** `docs/status/tv2_g1_graph_quality_2026-11-17.md`.

---

### Task 2: Chấm sheet đối chiếu của người (`agreement_human.csv`)

**Điều kiện:** D1-1 = (b).

**Files:**
- Modify: `src/vgar/evaluation/g1_labels.py` (thêm hàm, không đổi hàm cũ)
- Modify: `scripts/g1_evaluate.py:150-237` (thay khối agreement bằng lời gọi hàm mới)
- Test: `tests/test_g1_labels.py`

**Interfaces:**
- Produces:
  - `check_agreement(kit: Path, sheet: str, manifest: dict, items: dict[str, Item], labels: dict[str, Label], main_rows: dict[str, dict]) -> AgreementOutcome` trong `g1_labels.py`.
  - `@dataclass AgreementOutcome: exit_code: int | None` (None = tiếp tục; 2 = từ chối; 3 = còn mục lệch), `report: dict` (khóa `agreement`, `agreement_status`, `agreement_source`, `settlement`), `labels: dict[str, Label]` (nhãn cuối sau khi chốt).
  - Quy ước file theo `stem = Path(sheet).stem`: sheet mặc định `agreement_user.csv` giữ nguyên hành vi cũ (khóa `manifest["agreement_lock"]`, `disagreements.csv`, `settlement.csv`, `agreement_source = "claude_second_pass"`). Sheet khác: khóa `manifest["agreement_locks"][sheet]`, `disagreements_<stem>.csv`, `settlement_<stem>.csv`, `agreement_source = "human"`.
  - `g1_evaluate.py` thêm `--agreement-sheet` (mặc định `agreement_user.csv`). Với `agreement_source == "human"`, `NOTE` và markdown ghi "agreement with a human labeller" thay cho "separate Claude pass".

- [ ] **Step 1: Viết test hỏng**

```python
def test_human_sheet_locks_separately_and_keeps_user_lock(tmp_path):
    kit = _kit_with_agreement(tmp_path)          # helper: manifest with agreement_lock for agreement_user.csv
    _fill(kit / "agreement_human.csv", {"C001": "1", "N003": "1"})
    before = json.loads((kit / "manifest.json").read_text())["agreement_lock"]
    out = check_agreement(kit, "agreement_human.csv", *_inputs(kit))
    manifest = json.loads((kit / "manifest.json").read_text())
    assert out.report["agreement_source"] == "human"
    assert manifest["agreement_lock"] == before
    assert manifest["agreement_locks"]["agreement_human.csv"] == sha256_file(kit / "agreement_human.csv")

def test_human_sheet_disagreements_use_own_files(tmp_path):
    kit = _kit_with_agreement(tmp_path)
    _fill(kit / "agreement_human.csv", {"C001": "external", "N003": "1"})   # C001 differs from Claude's "1"
    out = check_agreement(kit, "agreement_human.csv", *_inputs(kit))
    assert out.exit_code == 3
    assert (kit / "disagreements_agreement_human.csv").exists() and not (kit / "disagreements.csv").exists()

def test_human_sheet_edit_after_first_use_is_refused(tmp_path):
    kit = _kit_with_agreement(tmp_path)
    _fill(kit / "agreement_human.csv", {"C001": "1", "N003": "1"})
    check_agreement(kit, "agreement_human.csv", *_inputs(kit))
    _fill(kit / "agreement_human.csv", {"C001": "external", "N003": "1"})
    assert check_agreement(kit, "agreement_human.csv", *_inputs(kit)).exit_code == 2

def test_default_sheet_behaviour_unchanged(tmp_path):
    kit = _kit_with_agreement(tmp_path)
    out = check_agreement(kit, "agreement_user.csv", *_inputs(kit))
    assert out.report["agreement_source"] == "claude_second_pass" and out.exit_code is None
```

`_kit_with_agreement` dựng kit tối thiểu 2 mục (`C001` lời gọi, `N003` tên dùng) bằng các hàm có sẵn (`write_sheet`, `write_agreement_sheet`, `lock`).

- [ ] **Step 2: Chạy, xác nhận hỏng** — `pytest tests/test_g1_labels.py -k "human_sheet or default_sheet"` → FAIL `ImportError: check_agreement`.
- [ ] **Step 3: Chuyển khối agreement của `g1_evaluate.main` vào `check_agreement`** theo quy ước file ở trên; `main` gọi hàm, trả `exit_code` nếu khác None, rồi dùng `outcome.labels`.
- [ ] **Step 4: Chạy lại** test mới và toàn bộ `tests/test_g1_labels.py` → PASS.
- [ ] **Step 5: Chạy thật trên kit hiện có, không đổi số cũ:** trong WSL `python scripts/g1_evaluate.py --kit ~/rt1/g1 --out ~/rt1/g1/report_check ...` (cùng cờ của hướng dẫn) → `g1_report.json` khớp `report/g1_report.json` ở mọi khóa `configurations`.
- [ ] **Step 6: Sau khi người dùng gán xong `agreement_human.csv`:** chạy với `--agreement-sheet agreement_human.csv --out ~/rt1/g1/report_human`; nếu mã 3, người dùng điền `settlement_agreement_human.csv`; cập nhật báo cáo Task 1 thêm mục "Độ khớp với người" (raw, kappa, mục lệch, mục đổi sau chốt).
- [ ] **Step 7: Cập nhật `docs/status/g1_labelling_guide.md`** thêm mục "Lượt người" (file, lệnh, file chốt riêng). Liệt kê file để người dùng commit: `src/vgar/evaluation/g1_labels.py`, `scripts/g1_evaluate.py`, `tests/test_g1_labels.py`, `docs/status/g1_labelling_guide.md`, báo cáo Task 1.

---

### Task 3: Nhãn ranh giới Component (component boundary quality)

**Điều kiện:** D1-2 = (a).

**Files:**
- Create: `scripts/g1_component_kit.py`
- Create: `src/vgar/evaluation/g1_components.py`
- Test: `tests/test_g1_components.py`

**Interfaces:**
- Produces:
  - `sample_components(documents: dict[str, dict], per_repo: int = 5, seed: int = 0) -> list[dict]` — mỗi phần tử `{component_id, repo, task_id, name, files}`; lấy tối đa `per_repo` Component mỗi repo, sắp theo id rồi xáo bằng `random.Random(seed)`.
  - Sheet `components.csv`: cột `component_id, repo, name, files, label, note`; `label` ∈ `correct | merge | split` (chữ thường, bỏ khoảng trắng).
  - `boundary_quality(rows: list[dict], seed: int = 0) -> dict` → `{"n", "correct", "merge", "split", "correct_rate", "ci95"}` (bootstrap 2.000 lần trên tỉ lệ `correct`); từ chối (`ValueError`) nếu có nhãn trống hoặc sai.
  - Kit ghi `components.md` (mỗi Component: tên, danh sách file, 10 cạnh `DEPENDS_ON` nặng nhất ra/vào) và khóa sheet bằng SHA-256 trong `components_manifest.json` khi chạy `--lock`.

- [ ] **Step 1: Viết test hỏng**

```python
def test_sample_is_capped_per_repo_and_deterministic():
    docs = {"r1": _doc(["a", "b", "c"]), "r2": _doc(["x"])}
    first = sample_components(docs, per_repo=2, seed=0)
    assert [c["repo"] for c in first].count("r1") == 2 and [c["repo"] for c in first].count("r2") == 1
    assert first == sample_components(docs, per_repo=2, seed=0)

def test_boundary_quality_counts_and_rate():
    rows = [{"label": "correct"}, {"label": "Merge "}, {"label": "correct"}, {"label": "split"}]
    result = boundary_quality(rows)
    assert (result["n"], result["correct"], result["merge"], result["split"]) == (4, 2, 1, 1)
    assert result["correct_rate"] == 0.5 and len(result["ci95"]) == 2

def test_boundary_quality_refuses_blank_or_unknown():
    with pytest.raises(ValueError):
        boundary_quality([{"label": ""}])
    with pytest.raises(ValueError):
        boundary_quality([{"label": "maybe"}])
```

- [ ] **Step 2: Chạy, xác nhận hỏng** (ImportError).
- [ ] **Step 3: Cài `sample_components`, `boundary_quality` và CLI `g1_component_kit.py --kit ~/rt1/g1 --out ~/rt1/g1/components [--lock] [--score]`** (graph build như `g1_evaluate`, cấu hình phục vụ mặc định).
- [ ] **Step 4: Chạy test** → PASS.
- [ ] **Step 5: Chạy kit trong WSL**, chép `components.csv` và `components.md` vào Downloads cho người dùng gán; sau khi gán: `--lock`, rồi `--score`; thêm dòng component boundary vào báo cáo Task 1.
- [ ] **Step 6: Liệt kê file để người dùng commit:** ba file trên và báo cáo Task 1.

---

### Task 4: `dependency_frontier_recall@B` theo `F*_approx`

**Điều kiện:** D2-4 = đo.

**Files:**
- Create: `src/vgar/evaluation/retrieval/frontier.py`
- Modify: `src/vgar/evaluation/retrieval/graph_arm.py` (sau `gold = extract_gold(...)` trong `evaluate_graph_task`)
- Modify: `src/vgar/evaluation/retrieval/scoring.py` (`score_record`, khối packed)
- Modify: `ablation_matrix/run_r1_ablation.py` (`METRICS` thêm `"packed_frontier_in_context"`)
- Test: `tests/test_frontier.py`

**Interfaces:**
- Produces:
  - `dependency_frontier(patch: str, gold: Mapping[str, Any], corpus: CorpusIndex) -> list[str]` — sắp xếp, không trùng; = `gold["gold_functions"]` ∪ `parent_id` của định nghĩa trong `corpus.definitions` có tên ngắn (phần sau dấu `.` cuối của qualname, sau `::`) xuất hiện như định danh (`\b[A-Za-z_]\w*\b`) ở dòng thêm của patch (bắt đầu `+`, không phải `+++`), với điều kiện tên ngắn đó có **đúng một** định nghĩa trong corpus; bỏ từ khóa Python và tên trong `builtins`.
  - `gold["frontier_functions"]: list[str]` do `evaluate_graph_task` thêm; các cánh văn bản dùng chung dict `gold` này.
  - `score_record` thêm `packed.metrics["frontier_in_context"] = |frontier ∩ p_funcs| / |frontier|` **chỉ khi** `gold` có khóa `frontier_functions` và nó không rỗng; `flat_metrics` tự thành `packed_frontier_in_context`.

- [ ] **Step 1: Viết test hỏng**

```python
PATCH = ("--- a/pkg/a.py\n+++ b/pkg/a.py\n@@ -1,2 +1,3 @@\n def f():\n-    return 1\n"
         "+    return helper(len(x)) + Unique().get()\n")

def test_frontier_adds_unique_names_from_added_lines():
    corpus = CorpusIndex({"pkg/a.py": "def f():\n    return 1\n", "pkg/b.py": "def helper():\n    pass\nclass Unique:\n    pass\n"})
    gold = {"gold_functions": ["pkg/a.py::pkg.a.f"]}
    assert dependency_frontier(PATCH, gold, corpus) == ["pkg/a.py::pkg.a.f", "pkg/b.py::pkg.b.Unique", "pkg/b.py::pkg.b.helper"]

def test_frontier_skips_names_with_several_definitions_and_builtins():
    corpus = CorpusIndex({"pkg/a.py": "def f():\n    return 1\n", "pkg/b.py": "def helper():\n    pass\n",
                          "pkg/c.py": "def helper():\n    pass\n"})
    gold = {"gold_functions": ["pkg/a.py::pkg.a.f"]}
    assert dependency_frontier(PATCH, gold, corpus) == ["pkg/a.py::pkg.a.f"]      # helper twice, len builtin

def test_frontier_equals_gold_when_patch_adds_no_names():
    corpus = CorpusIndex({"pkg/a.py": "def f():\n    return 1\n"})
    patch = "--- a/pkg/a.py\n+++ b/pkg/a.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 1\n+    return 2\n"
    assert dependency_frontier(patch, {"gold_functions": ["pkg/a.py::pkg.a.f"]}, corpus) == ["pkg/a.py::pkg.a.f"]

def test_score_record_reports_frontier_only_when_present():
    record = _record(["pkg/a.py::pkg.a.f", "pkg/b.py::pkg.b.helper"])
    base = {"gold_files": ["pkg/a.py"], "gold_functions": ["pkg/a.py::pkg.a.f"]}
    without = score_record(record, base, budget_tokens=12000, counter=bytes_div4_counter, counter_label="x")
    assert "frontier_in_context" not in without["packed"]["metrics"]
    with_frontier = score_record(record, {**base, "frontier_functions": ["pkg/a.py::pkg.a.f", "pkg/c.py::pkg.c.g"]},
                                 budget_tokens=12000, counter=bytes_div4_counter, counter_label="x")
    assert with_frontier["packed"]["metrics"]["frontier_in_context"] == 0.5
```

Kiểm định dạng `parent_id` thật của `CorpusIndex` trước khi chốt chuỗi kỳ vọng; nếu khác, sửa chuỗi trong test cho khớp định dạng `path::qualname` mà gold đang dùng.

- [ ] **Step 2: Chạy, xác nhận hỏng.**
- [ ] **Step 3: Cài `dependency_frontier`, gắn vào `evaluate_graph_task`, thêm metric vào `score_record`, thêm tên metric vào `METRICS`.**
- [ ] **Step 4: Chạy** `tests/test_frontier.py`, `tests/test_graph_retrieval.py`, `ablation_matrix/tests/` → PASS; hash config ranking ghim trong `tests/test_graph_retrieval.py` không đổi.
- [ ] **Step 5: Liệt kê file để người dùng commit.**

---

### Task 5: Cánh `embedding` trong R1

**Điều kiện:** D2-1 (model theo đề xuất).

**Files:**
- Create: `ablation_matrix/embedding_baseline.py`
- Modify: `ablation_matrix/run_r1_ablation.py` (`TEXT_ARMS`, `PAIRS`, `evaluate_task`, `parse_args`)
- Test: `ablation_matrix/tests/test_embedding_baseline.py`

**Interfaces:**
- Produces:
  - `class Embedder(Protocol): model_id: str; revision: str; def encode(self, texts: list[str], *, query: bool) -> list[list[float]]`.
  - `class SentenceTransformerEmbedder` (cài `Embedder`): `__init__(model_id: str, revision: str, *, device: str = "cuda", batch_size: int = 32)`; `trust_remote_code=True`; khi `query=True` thêm tiền tố truy vấn của Global Constraints; vector chuẩn hóa L2. Import `sentence_transformers` **bên trong** `__init__` để CI không cần thư viện.
  - `class EmbeddingCache`: `__init__(folder: Path)`; `get_many(keys: list[str]) -> dict[str, list[float]]`; `put_many(items: dict[str, list[float]]) -> None`; khóa = `sha256(model_id + "\0" + revision + "\0" + chunk_id + "\0" + sha256(snippet))`; lưu một file `.npy` hoặc JSON mỗi corpus, ghi nguyên tử.
  - `embedding_rank(instance_id: str, issue_text: str, sources: Mapping[str, str], embedder: Embedder, *, cache: EmbeddingCache | None = None) -> RankRecord` — arm `"embedding"`; cùng `extract_chunks(dict(sources))` với BM25; xếp **toàn bộ** chunk theo cosine giảm dần, hòa thì theo `(path, start_line)`; `meta` = `{"model_id", "revision", "corpus_chunks", "cache_hits", "parse_failures"}`.
  - `run_r1_ablation.py`: cờ `--embedding-model`, `--embedding-revision`, `--embedding-cache` (Path), `--embedding-device` (mặc định `cuda`). Không có `--embedding-model` thì cánh không chạy và kết quả giống hệt trước. `TEXT_ARMS = ("bm25", "grep", "neighbor", "embedding")`; `PAIRS` thêm `("no_task_trace", "embedding")`, `("task_trace", "embedding")`, `("task_trace_rt1", "embedding")`, `("task_trace_rt1", "bm25")`, `("task_trace_rt1", "grep")`.

- [ ] **Step 1: Viết test hỏng** (embedder giả: vector = số lần xuất hiện của 3 từ cố định)

```python
class Fake:
    model_id, revision = "fake", "r0"
    def encode(self, texts, *, query):
        return [[t.count("alpha"), t.count("beta"), t.count("gamma") + 0.001] for t in texts]

SOURCES = {"pkg/a.py": "def one():\n    alpha = 1\n", "pkg/b.py": "def two():\n    beta = 2\n"}

def test_ranks_every_chunk_by_cosine():
    record = embedding_rank("t", "beta problem", SOURCES, Fake())
    assert record.arm == "embedding" and record.items[0].path == "pkg/b.py"
    assert len(record.items) == record.meta["corpus_chunks"]

def test_same_chunks_as_bm25_corpus():
    ours = [i.item_id for i in embedding_rank("t", "alpha", SOURCES, Fake()).items]
    assert sorted(ours) == sorted(c["chunk_id"] for c in extract_chunks(dict(SOURCES))[0])

def test_cache_is_keyed_by_model_and_revision(tmp_path):
    cache = EmbeddingCache(tmp_path)
    embedding_rank("t", "alpha", SOURCES, Fake(), cache=cache)
    other = Fake(); other.revision = "r1"
    record = embedding_rank("t", "alpha", SOURCES, other, cache=cache)
    assert record.meta["cache_hits"] == 0
    assert embedding_rank("t", "alpha", SOURCES, Fake(), cache=cache).meta["cache_hits"] == record.meta["corpus_chunks"]

def test_runner_without_embedding_flag_has_no_embedding_arm():
    args = parse_args(["root", "manifest.json", "--out", "o", "--allow-fallback-counter"])
    assert args.embedding_model is None
```

So với toàn bộ `extract_chunks`, không với danh sách BM25, vì BM25 có thể bỏ chunk điểm 0.

- [ ] **Step 2: Chạy, xác nhận hỏng.**
- [ ] **Step 3: Cài `embedding_baseline.py` và nối vào runner** (tạo embedder một lần trong `main`, truyền vào `evaluate_task`; `_text_arm` dùng lại nguyên).
- [ ] **Step 4: Chạy** `ablation_matrix/tests/` → PASS.
- [ ] **Step 5: Liệt kê file để người dùng commit.**

---

### Task 6: RRF (kết quả phụ) và hiệu chỉnh Holm trong `summarize`

**Files:**
- Create: `ablation_matrix/fusion.py`
- Modify: `ablation_matrix/run_r1_ablation.py` (`summarize`)
- Test: `ablation_matrix/tests/test_fusion.py`

**Interfaces:**
- Produces:
  - `ranked_lists(arm_result: dict) -> tuple[list[str], list[str]]` — file và hàm theo thứ tự xuất hiện lần đầu trong `arm_result["ranked"]`; hàm chỉ lấy mục `kind ∈ {function, method}` có `function_id`.
  - `rrf(lists: list[list[str]], k: int = 60) -> list[str]` — điểm `Σ 1 / (k + rank)`, hòa thì theo chuỗi tăng dần.
  - `fused_metrics(task: dict, members: tuple[str, ...]) -> dict[str, float | None]` — khóa `file_recall@1`, `file_recall@5`, `function_recall@5`, `function_recall@10`, `function_mrr`, trên `task["gold"]`; trả `{}` nếu thiếu cánh nào trong `members`.
  - `FUSIONS = {"rrf_graph_bm25_neighbor": ("task_trace_rt1", "bm25", "neighbor"), "rrf_bm25_neighbor": ("bm25", "neighbor")}`; thêm `"rrf_graph_embedding": ("task_trace_rt1", "embedding")` và `"rrf_embedding_bm25": ("embedding", "bm25")` khi có cánh embedding.
  - `summarize` trả thêm khóa `"secondary": {"note": "analysis beyond the proposal", "means": {...}, "pairs": {"rrf_graph_bm25_neighbor - rrf_bm25_neighbor": {...}}}`; `means` và `pairs` cũ giữ nguyên.
  - Holm (spec §3.1; nguồn: plan, không phải proposal): `bootstrap_p(deltas: list[float], seed: int, rounds: int = 2000) -> float` = `min(1, 2 * min(frac(mean* <= 0), frac(mean* >= 0)))` trên cùng các mẫu bootstrap với `_bootstrap`; `holm_adjust(pvalues: dict[str, float]) -> dict[str, float]` (Holm–Bonferroni bước xuống, giữ đơn điệu, chặn ở 1). `PRIMARY_PAIRS = (("task_trace_rt1", "bm25"), ("task_trace_rt1", "embedding"), ("task_trace_rt1", "grep"), ("task_trace", "no_task_trace"))`; `PRIMARY_METRICS = ("file_recall@1", "file_recall@5", "function_recall@5", "function_mrr", "packed_gold_function_in_context", "packed_frontier_in_context")`. `summarize` trả thêm `"primary": {pair: {metric: {"mean_delta", "ci95", "p", "p_holm"}}}`, Holm áp trên toàn bộ ô (cặp × metric) có dữ liệu.

- [ ] **Step 1: Viết test hỏng**

```python
def test_rrf_scores_and_ties():
    assert rrf([["a", "b"], ["b", "c"]]) == ["b", "a", "c"]

def test_ranked_lists_dedupe_and_function_kinds():
    arm = {"ranked": [{"path": "p.py", "kind": "method", "function_id": "p.py::C.m"},
                      {"path": "p.py", "kind": "class", "function_id": "p.py::C"},
                      {"path": "q.py", "kind": "function", "function_id": "q.py::f"}]}
    assert ranked_lists(arm) == (["p.py", "q.py"], ["p.py::C.m", "q.py::f"])

def test_fused_metrics_empty_when_member_missing():
    assert fused_metrics({"arms": {"bm25": {"ranked": []}}, "gold": {"gold_files": [], "gold_functions": []}},
                         ("bm25", "neighbor")) == {}

def test_holm_adjust_hand_computed():
    assert holm_adjust({"a": 0.01, "b": 0.04, "c": 0.03}) == pytest.approx({"a": 0.03, "b": 0.06, "c": 0.06})

def test_bootstrap_p_all_positive_is_small():
    assert bootstrap_p([0.2] * 30, seed=0) == 0.0 and bootstrap_p([0.0] * 30, seed=0) == 1.0

def test_summarize_old_run_keeps_tables(tmp_path):
    _write_task(tmp_path, arms=("bm25", "grep", "neighbor", "task_trace_rt1"))   # no embedding arm
    summary = summarize(tmp_path)
    assert "embedding" in summary["means"] and all(v is None for v in summary["means"]["embedding"].values())
    assert "rrf_graph_embedding" not in summary["secondary"]["means"]
```

- [ ] **Step 2: Chạy, xác nhận hỏng.**
- [ ] **Step 3: Cài `fusion.py`, gọi từ `summarize`** (bootstrap bằng `_bootstrap` có sẵn).
- [ ] **Step 4: Chạy test** → PASS.
- [ ] **Step 5: Đối chiếu với báo cáo R1 trên lượt có sẵn:** trong WSL chạy `summarize` trên `~/rt1/results/r1_50` → `rrf_graph_bm25_neighbor`: file R@1 0,447, hàm R@5 0,536, hàm MRR 0,445; chênh với `rrf_bm25_neighbor`: R@1 file +0,140 [+0,06; +0,24] (bảng phần 4 của `docs/status/tv2_r1_results_comparison_2026-11-16.md`). Lệch thì dừng và tìm nguyên nhân.
- [ ] **Step 6: Liệt kê file để người dùng commit.**

---

### Task 7: Cổng held-out theo protocol, đếm task held-out đủ điều kiện

**Files:**
- Modify: `src/vgar/evaluation/heldout_gate.py`
- Modify: `src/vgar/evaluation/retrieval/dataset.py:43` (truyền protocol của manifest)
- Modify: `scripts/prepare_manifest.py` (cờ `--protocol`)
- Modify: `ablation_matrix/run_r1_ablation.py:340` (cờ `--allow-heldout`)
- Create: `scripts/count_heldout_eligible.py`
- Test: `tests/test_heldout_gate.py`

**Interfaces:**
- Produces:
  - `PROTOCOLS = {"repair": ("docs/protocol_freeze_heldout.md", "protocol-freeze"), "r1": ("docs/protocol_freeze_r1_heldout.md", "protocol-freeze-r1")}`.
  - `latest_freeze_tag(repo, protocol="repair")`, `freeze_sha256(repo, protocol="repair")`, `assert_heldout_unlocked(manifest, *, repo=None, command=None)` đọc `manifest.get("freeze_protocol", "repair")`; regex tag `^<tag>(?:-amend-(\d+))?$` theo protocol; log ghi thêm `"protocol"`. Hằng `FREEZE_FILE`, `TAG` giữ nguyên làm giá trị của `"repair"`.
  - `prepare_manifest.py --protocol {repair,r1}` (mặc định `repair`) ghi `manifest["freeze_protocol"]`.
  - `count_heldout_eligible.py <parquet>` in số task held-out và số task có `len(changed_source_files(patch)) >= 1` và `>= 2`, theo repo; chỉ đọc cột `instance_id`, `repo`, `patch`; chỉ dùng `changed_source_files` (đường dẫn file), không in nội dung; ghi một dòng vào `results/heldout_access.log` với `"command": "count_heldout_eligible"`.

- [ ] **Step 1: Viết test hỏng** (tái dùng helper repo git tạm của `tests/test_heldout_gate.py`)

```python
def test_r1_tag_does_not_unlock_repair(tmp_path):
    repo = _repo_with_files(tmp_path, {"docs/protocol_freeze_r1_heldout.md": "r1"})
    _tag(repo, "protocol-freeze-r1")
    assert latest_freeze_tag(repo, "r1") == "protocol-freeze-r1"
    assert latest_freeze_tag(repo, "repair") is None

def test_repair_tag_does_not_unlock_r1(tmp_path):
    repo = _repo_with_files(tmp_path, {"docs/protocol_freeze_heldout.md": "repair"})
    _tag(repo, "protocol-freeze")
    assert latest_freeze_tag(repo, "r1") is None

def test_manifest_protocol_selects_freeze_file(tmp_path):
    repo = _repo_with_files(tmp_path, {"docs/protocol_freeze_r1_heldout.md": "r1"})
    _tag(repo, "protocol-freeze-r1")
    manifest = {"freeze_protocol": "r1", "freeze_sha256": freeze_sha256(repo, "r1")}
    assert_heldout_unlocked(manifest, repo=repo)                        # no error
    with pytest.raises(ValueError):
        assert_heldout_unlocked({**manifest, "freeze_protocol": "repair"}, repo=repo)

def test_r1_amendment_tag_wins(tmp_path):
    repo = _repo_with_files(tmp_path, {"docs/protocol_freeze_r1_heldout.md": "r1"})
    _tag(repo, "protocol-freeze-r1"); _tag(repo, "protocol-freeze-r1-amend-2")
    assert latest_freeze_tag(repo, "r1") == "protocol-freeze-r1-amend-2"
```

- [ ] **Step 2: Chạy, xác nhận hỏng.**
- [ ] **Step 3: Tham số hóa cổng, thêm cờ, viết script đếm.**
- [ ] **Step 4: Chạy** `tests/test_heldout_gate.py`, `tests/m2/test_dataset_split.py` → PASS (test cũ của repair không đổi).
- [ ] **Step 5: Người dùng chạy** `python scripts/count_heldout_eligible.py ~/w9/dataset/test-00000-of-00001.parquet` trong WSL; ghi hai con số (≥ 1 file, ≥ 2 file) vào spec D3-1 để nhóm quyết.
- [ ] **Step 6: Liệt kê file để người dùng commit.**

---

### Task 8: Chạy embedding và frontier trên 50 task dev, cập nhật báo cáo R1

**Điều kiện:** Task 4, 5, 6 xong; D2-3 = có.

**Files:**
- Modify: `docs/status/tv2_r1_results_comparison_2026-11-16.md` (thêm cột/hàng, không xóa số cũ)
- Create: `docs/status/tv2_r1_embedding_dev_2026-11-<ngày>.md`

- [ ] **Step 1: Người dùng cài môi trường:** `~/.vgar-wsl/bin/pip install "sentence-transformers==<bản ghim>" torch --index-url https://download.pytorch.org/whl/cu121`; ghi phiên bản vào báo cáo; lấy revision SHA của `nomic-ai/CodeRankEmbed` bằng `huggingface_hub.model_info(...).sha`.
- [ ] **Step 2: Người dùng chạy** (WSL, attached, `tee` log):
  `PYTHONPATH=<repo>/src ~/.vgar-wsl/bin/python <repo>/ablation_matrix/run_r1_ablation.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json --out ~/rt1/results/r1_emb50 --allow-fallback-counter --prune --embedding-model nomic-ai/CodeRankEmbed --embedding-revision <sha> --embedding-cache ~/rt1/emb_cache | tee ~/rt1/r1_emb50.log`.
- [ ] **Step 3: Kiểm tra lượt chạy:** 50/50 SUCCEEDED; `corpus_hash` của `embedding` trùng `bm25` ở mọi task; số của 9 cấu hình cũ trùng `r1_50` (so `summary.json`, mọi ô).
- [ ] **Step 4: Viết báo cáo:** bảng A–F thêm hàng `embedding`; bảng cặp thêm các cặp embedding; cột `packed_frontier_in_context` (ghi "xấp xỉ của `F*`"); phần RRF ghi "phân tích thêm ngoài proposal"; mục baseline còn thiếu: "agent default exploration" (D2-2) kèm việc đã đề nghị TV1.
- [ ] **Step 5: Liệt kê file để người dùng commit.**

---

### Task 9: File freeze cho R1

**Điều kiện:** Task 1, 7, 8 xong; D3-1, D3-2 đã quyết.

**Files:**
- Create: `docs/protocol_freeze_r1_heldout.md`

- [ ] **Step 1: Viết file** theo bảng §3.1 của spec, điền giá trị thật: commit (để trống cho đến khi tag), parquet hash (`sha256:a45b1fe4…` như file freeze repair), chính sách chia split, lọc D3-1 kèm số đếm Task 7, 9 cấu hình + `embedding` (model id + revision SHA), layer và cờ tắt, ngân sách 12.000, bộ đếm, hash `RT1_CONFIG`, metric chính, cặp chính, thống kê (ghi nguồn: plan, không phải proposal), RRF là kết quả phụ, quy tắc chạy lại task lỗi hạ tầng (spec §3.2 bước 5), lệnh chạy đầy đủ.
- [ ] **Step 2: Kiểm tra** mỗi ô có giá trị cụ thể hoặc ghi rõ "điền khi tag"; không còn "ĐANG CHỜ" nào khác.
- [ ] **Step 3: Người dùng gửi nhóm duyệt; sau khi cả ba approve, người dùng tạo annotated tag `protocol-freeze-r1` trên commit merge.**

---

### Task 10: Chạy R1 trên held-out đúng một lần và viết báo cáo

**Điều kiện:** tag `protocol-freeze-r1` đã có.

**Files:**
- Create: `docs/status/tv2_r1_heldout_<ngày>.md`

- [ ] **Step 1: Người dùng tạo manifest:** `python scripts/prepare_manifest.py <root> --split heldout --allow-heldout --protocol r1 --min-source-files <D3-1> --count <số đếm Task 7>`; kiểm tra `freeze_protocol == "r1"` và `freeze_sha256` trong manifest.
- [ ] **Step 2: Người dùng chạy một lượt** đúng lệnh trong file freeze, thêm `--allow-heldout`, attached và `tee` log (ước tính khoảng 7,5 giờ cộng phần embedding).
- [ ] **Step 3: Task lỗi hạ tầng:** chạy lại đúng task đó trên cùng commit bằng `--only`; ghi vào báo cáo; không đổi cấu hình.
- [ ] **Step 4: Viết báo cáo:** metric chính và cặp chính với CI95 và Holm; bảng phụ RRF ghi "phân tích thêm ngoài proposal"; mỗi số kèm lệnh tái tạo; nhật ký `results/heldout_access.log`.
- [ ] **Step 5: Liệt kê file để người dùng commit.**
