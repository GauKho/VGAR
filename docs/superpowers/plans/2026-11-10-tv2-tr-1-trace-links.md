# TV2 · TR-1: trace links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tách `build_trace_links`, nối frame, failing test, error message tới code bằng `RESOLVES_TO`, đưa frame tuyệt đối thành anchor, và có công cụ đo trace link P/R cho G1.

**Architecture:** `grounding.py` có hàm thuần tìm file của frame tuyệt đối, dùng chung cho anchor và trace link. `graph/trace_links.py` là luật thuần, `TaskOverlayBuilder` chỉ đổi `TraceLink` thành cạnh. `evaluation/trace_quality.py` tính điểm thuần, `scripts/measure_trace_links.py` chạy trên manifest.

**Tech Stack:** Python 3.11+, pytest, git CLI.

**Spec:** `docs/superpowers/specs/2026-11-10-tv2-tr-1-trace-links-design.md`

## Global Constraints

- Chỉ dùng plan 2 tuần và proposal làm căn cứ; code có sẵn chỉ là hiện trạng.
- `SCHEMA_VERSION = "vgar-schema-full-v5"`; profile `task-overlay-v11-trace-links`.
- `rule_id`: `task.traces_to.v1`, `task.resolves_to.frame.v1`, `task.resolves_to.failing_test.v1`, `task.resolves_to.error.v1`.
- Confidence frame `0.95 / 0.8 / 0.7 / 0.6`; error `0.9 / 0.6`. Mốc đo chính `0.7`; bootstrap `rounds=2000`, `seed=0`.
- Module mới trong `src/vgar`: `logger = logging.getLogger(__name__)`, không in ra stdout; docstring có Args.
- Không đổi `TRACES_TO`, không lọc cạnh Issue → Component, không sửa test GT-1 trừ assert `SCHEMA_VERSION`.
- Không truyền `FAIL_TO_PASS` vào công cụ đo.
- **Không `git commit`, không `git push`.** Không đưa `artifacts/sample_graph.db` và file lạ `olve --agent ...` vào commit. Không sửa `src` khi suite đang chạy; suite bị dừng vì thiếu RAM thì báo người dùng, không tự chạy lại.
- Lệnh test: `python -m pytest -q -p no:cacheprovider <file>`.

## Review Focus

1. Graph không có Component: `score_task` không lỗi, baseline ngẫu nhiên bỏ qua task đó (Task 3).
2. `bases` có `metaclass=ABCMeta`, `Generic[T]`, `pkg.Base`: không lỗi, chỉ xét tên lớp (Task 2).
3. Nhóm không có task hoặc không có cạnh: không chia cho 0; precision là `None` khi không có cạnh, recall là `None` khi không có đáp án, còn có đáp án mà không có cạnh thì recall là 0 (Task 3).
4. Đường dẫn có cả hai `site-packages`: lấy phần sau lần cuối (Task 1).
5. Checkout thiếu thư mục: bỏ task, ghi lại, không dừng cả lượt chạy (Task 4).

---

### Task 1: Schema và anchor từ frame tuyệt đối

**Files:** Modify `src/vgar/contracts/schema.py`, `src/vgar/graph/grounding.py:297-298`, `tests/test_task_graph.py:42`, `tests/test_code_graph.py:47`. Test: `tests/test_trace_links.py`.

**Interfaces — Produces:**

```python
def is_absolute_path(path: str) -> bool: ...   # bắt đầu bằng "/" hoặc ổ đĩa "C:"
def resolve_absolute_frame(path: str, files: Collection[str]) -> str | None: ...   # path đã đổi "\\" thành "/"
```

- [ ] **Step 1: Viết test fail** (`files = {"requests/api.py", "src/flask/app.py", "lib/mpl/x.py", "requests/packages/urllib3/c.py", "test_requests.py", "a/b/m.py", "b/m.py"}`):

```python
@pytest.mark.parametrize(("path", "expected"), [
    ("/L/site-packages/requests/api.py", "requests/api.py"),
    ("/L/dist-packages/flask/app.py", "src/flask/app.py"),
    ("/L/site-packages/mpl/x.py", "lib/mpl/x.py"),
    ("/L/site-packages/urllib3/c.py", None),
    ("/a/site-packages/x/site-packages/requests/api.py", "requests/api.py"),
    ("/usr/lib/python2.7/requests/api.py", None),
    ("C:/Python38/Lib/a/b/m.py", None),
    ("/Users/me/test_requests.py", None),
    ("/home/me/proj/a/b/m.py", "a/b/m.py"),
    ("C:/work/a/b/m.py", "a/b/m.py"),
    ("/home/me/../a/b/m.py", None),
])
def test_resolve_absolute_frame(path, expected) -> None:
    assert resolve_absolute_frame(path, FILES) == expected

def test_schema_declares_resolves_to() -> None: ...  # đủ 7 cặp của spec §5; TRACES_TO vẫn 2 cặp; SCHEMA_VERSION v5
def test_absolute_traceback_becomes_path_line_anchor(tmp_path) -> None: ...  # pkg/m.py có def f; issue 'File "/x/site-packages/pkg/m.py", line 1, in f' → anchor f, score 0.95, kind path_line
def test_absolute_path_in_prose_is_still_ignored(tmp_path) -> None: ...      # issue "see /x/site-packages/pkg/m.py:1" → không có evidence kind path_line; đường dẫn nằm trong unmatched_locations
def test_issue_without_absolute_traceback_keeps_anchors(tmp_path) -> None: ...  # frame tương đối cho anchor như _match_paths
```

- [ ] **Step 2:** Chạy `tests/test_trace_links.py` → FAIL vì chưa có hàm.
- [ ] **Step 3:** Viết hai hàm theo bảng §4.2: `..` → None; `site-packages`/`dist-packages` lấy lần cuối, phải đúng một trong `rest`, `src/rest`, `lib/rest`; `re.search(r"/python\d+(?:\.\d+)?/", path, re.I)` → None; còn lại path repo dài nhất có `/`, thỏa `path.endswith("/" + item)`. Tại dòng 298: nếu `pattern is _TRACEBACK and is_absolute_path(path)` thì `paths = [resolved] if resolved else []`, không thì `_match_paths`.
- [ ] **Step 4:** Thêm `"RESOLVES_TO"` vào `EDGE_ENDPOINTS` (ghi chú "Proposed, pending team review; proposal line 548"), đổi `SCHEMA_VERSION`, sửa hai assert v4 → v5.
- [ ] **Step 5:** Chạy `tests/test_trace_links.py tests/test_task_graph.py tests/test_code_graph.py` → PASS.

---

### Task 2: `build_trace_links` và overlay

**Files:** Create `src/vgar/graph/trace_links.py`. Modify `src/vgar/graph/task_overlay.py`. Test: `tests/test_trace_links.py`.

**Interfaces — Consumes:** Task 1. **Produces:** `TraceLink` (`edge_type, source_id, target_id, confidence, rule_id, evidence, properties`), `build_trace_links(issue_id, task_nodes, grounding, nodes) -> list[TraceLink]`, `rank_component_traces(edges) -> list[dict]` đúng như spec §4.

- [ ] **Step 1: Viết test fail**, dùng node dict tự dựng và `AnchorResult("v", [], [], [])`:

```python
def test_frame_named_symbol_containing_line() -> None: ...       # Function "f" dòng 1-5, line 3, function "f" → f, 0.95, rule frame
def test_frame_line_drift_unique_name() -> None: ...             # line 99, đúng một symbol "f" → f, 0.8
def test_frame_module_goes_to_file() -> None: ...                # "<module>" và None → File, 0.7
def test_frame_unknown_function_goes_to_file() -> None: ...      # "g" → File, 0.6
def test_frame_evidence() -> None: ...                           # [{"kind": "frame_location", "file": ..., "line": ...}]; line là str vì evidence là dict[str, str]
def test_relative_frame_rules() -> None: ...                     # a/m.py khớp x/a/m.py; hai file cùng đuôi → không cạnh; "m.py" chỉ khớp m.py ở gốc
def test_stdlib_and_user_script_frames_have_no_edge() -> None: ...
def test_failing_test_links_use_anchor_score() -> None: ...      # test_node_ids 1 id, anchor score 1.0, evidence kind test_selector
def test_error_qualified_name() -> None: ...                     # "p.m.FooError" → 0.9
def test_error_builtin_bare_name_has_no_edge() -> None: ...      # repo có Class ConnectionError(Exception), "ConnectionError" → không cạnh
def test_error_dotted_reexport_uses_last_part() -> None: ...     # "p.ConnectionError", một Class exception → 0.6
def test_error_requires_exception_class() -> None: ...           # Class FooError bases [] → không cạnh
def test_error_inherited_chain() -> None: ...                    # C(B), B(Exception) → 0.6; C(p.B) cũng 0.6
def test_error_inheritance_cycle() -> None: ...                  # A(B), B(A) → không cạnh, không treo
def test_error_odd_bases() -> None: ...                          # ["metaclass=ABCMeta", "Generic[T]", "Exception"] → 0.6
def test_error_same_name_twice() -> None: ...                    # hai Class trùng tên → không cạnh
def test_rank_component_traces() -> None: ...                    # (0.8,1),(0.75,9),(0.8,2),(0.8,2,id nhỏ hơn) → conf, count, id
def test_weak_component_edge_is_kept() -> None: ...              # overlay thật, anchor 0.45 vẫn có TRACES_TO
def test_frame_edge_rejected_as_traces_to() -> None: ...         # validate_graph_document báo lỗi endpoint
def test_windows_backslash_frame() -> None: ...                  # r"C:\work\a\b\m.py" khớp a/b/m.py
def test_relative_frame_with_parent_segment() -> None: ...       # "../a/m.py" → không cạnh
def test_overlay_has_resolves_to_and_new_profile() -> None: ...  # ISSUE của test_task_graph trên multi_package: frame app/service.py:8 → Function login, 0.95, rule frame; overlay_id == _digest({"graph_version": ..., "task_id": "t1", "issue_text": ISSUE, "failing_tests": [], "labels": [], "profile": "task-overlay-v11-trace-links"})
def test_overlay_edges_are_stable() -> None: ...                 # build hai lần cho cùng danh sách cạnh, sắp theo (type, source_id, target_id)
```

- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Viết `trace_links.py`. Chuyển nguyên logic `_add_traces` và `_MAX_TRACE_EVIDENCE` sang; `properties={"anchor_count": n}`. Exception có sẵn: tên trong `builtins` là lớp con `BaseException`. Tên lớp từ `bases`: bỏ mục có `=`, cắt `[...]`, lấy phần sau dấu chấm cuối. Dùng `_contains_line` và `_SYMBOL_TYPES` của `grounding`. Chọn đích của frame: xét `function` trống hoặc bắt đầu bằng `<` trước; dòng 1 của bảng lọc symbol chứa dòng và có `name == function`, rồi lấy symbol có `end_byte - start_byte` nhỏ nhất. `evidence` của frame ghi `line` dạng chuỗi. File lấy từ các node `File`.
- [ ] **Step 4:** Sửa `task_overlay.py`: `_edge(..., rule_id: str | None = None)`; xóa `_add_traces`, tham số `ambiguous` của `_add_task_facts`, `defaultdict`, `_MAX_TRACE_EVIDENCE`; ngay sau dòng gọi `_add_task_facts`, trước `edges.sort`, thêm các cạnh từ `build_trace_links(issue["id"], task_nodes, grounding, self._document["nodes"])`, truyền `rule_id=link.rule_id`; đổi profile.
- [ ] **Step 5:** Chạy `tests/test_trace_links.py tests/test_task_graph.py` → PASS, không sửa test GT-1.

---

### Task 3: `trace_quality`

**Files:** Create `src/vgar/evaluation/trace_quality.py`. Test: `tests/test_trace_quality.py`.

**Interfaces — Consumes:** `rank_component_traces`. **Produces:** `RankedTrace`, `TraceScore`, `score_task(document, overlay, gold_files) -> TraceScore`, `summarise(scores, seed=0, rounds=2000) -> dict` như spec §6. Dạng trả về: `{"all"|"with_traceback"|"without_traceback": {"n", "component": {"all", "confidence_0.5", "confidence_0.6", "confidence_0.7", "confidence_0.8", "top1", "top2"}, "mrr", "top_ties", "baselines": {"random_precision", "largest_component"}, "file", "ci95": {"confidence_0.7"|"top1"|"largest_component": {"precision": [lo, hi]|None, "recall": ...}}}}`; mỗi view là `{"kept", "correct", "gold", "precision", "recall"}`.

- [ ] **Step 1: Viết test fail.** T1: traceback False, components 4, gold_components 1, largest đúng, traces `(0.95,T),(0.75,F),(0.4,F)`, không hòa, mentioned 10/1, gold_files 1. T2: traceback True, components 10, gold_components 2, largest sai, traces `(0.75,F),(0.75,T)`, hòa, mentioned 5/1, gold_files 2.

```python
def test_summarise_hand_numbers() -> None:
    all_ = summarise([T1, T2])["all"]
    c = all_["component"]
    assert (c["all"]["kept"], c["all"]["correct"], c["all"]["gold"]) == (5, 2, 3) and c["all"]["precision"] == pytest.approx(0.4)
    assert c["confidence_0.7"]["precision"] == pytest.approx(0.5) and c["confidence_0.7"]["recall"] == pytest.approx(2 / 3)
    assert c["confidence_0.8"]["precision"] == 1.0 and c["top1"]["recall"] == pytest.approx(1 / 3)
    assert c["top2"]["kept"] == 4 and all_["mrr"] == pytest.approx(0.75) and all_["top_ties"] == 1
    assert all_["baselines"]["random_precision"] == pytest.approx(0.225)
    assert all_["baselines"]["largest_component"]["precision"] == pytest.approx(0.5)
    assert all_["file"]["precision"] == pytest.approx(2 / 15)

def test_groups_split_on_traceback() -> None: ...       # n của with/without đều 1
def test_empty_group_has_none() -> None: ...            # summarise([T1])["with_traceback"]: n 0, precision None, mrr None
def test_same_seed_same_interval() -> None: ...
def test_single_task_interval_is_the_point() -> None: ...
def test_score_task_on_real_overlay() -> None: ...      # multi_package, gold ["app/service.py"]: correct, gold_components 1, has_traceback True
def test_score_task_without_components() -> None: ...   # bỏ Component như test_graph_without_components: components 0, largest False, random bỏ qua task này
def test_largest_tie_uses_smallest_id() -> None: ...
def test_top_tied_needs_same_confidence_and_count() -> None: ...
```

- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Viết module. `has_traceback` là overlay có node `StackTraceFrame`. `top_tied` là hai cạnh đầu cùng `confidence` và `anchor_count`. MRR tính trên mọi cạnh, task không có cạnh đúng là 0. Top-k lấy trong các cạnh ≥ 0.7. Baseline nhiều file nhất: mỗi task có Component tính 1 cạnh, `gold` là tổng `gold_components`; baseline ngẫu nhiên bỏ task `components == 0`. File đề cập: tập `path` của target `MENTIONS`, bỏ `PythonGraphBuilder._is_test_path`; `mentioned_correct` là phần giao với `gold_files`. Bootstrap: `rng.choices(scores, k=n)`, bỏ vòng có giá trị `None`, phân vị `[v[int(0.025*len(v))], v[int(0.975*len(v))-1]]`.
- [ ] **Step 4:** Chạy → PASS.

---

### Task 4: `scripts/measure_trace_links.py`

**Files:** Create script. Test: `tests/test_measure_trace_links.py` (nạp bằng `importlib.util.spec_from_file_location`).

**Interfaces — Produces:** `measure(manifest: dict, repositories: Path, allow_heldout: bool = False) -> dict` với khóa `tasks`, `skipped`, `summary`; `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Viết test fail** (repo git thật trong `tmp_path/<instance_id>`, commit bằng `git -c user.name=t -c user.email=t@t commit`; chọn id dạng `a__b-<i>` theo `split_of`; task có `repo: "a/b"`, `base_commit`, `problem_statement`, `changed_source_files`, `split`):

```python
def test_measure_dev_task(tmp_path) -> None: ...             # tasks có 1 dòng, skipped rỗng
def test_empty_or_duplicate_manifest_is_refused(tmp_path) -> None: ...  # ValueError, như evaluate_manifest
def test_refuses_heldout_manifest(tmp_path) -> None: ...     # pytest.raises(ValueError)
def test_refuses_heldout_task_in_dev_manifest(tmp_path) -> None: ...
def test_head_mismatch_is_skipped(tmp_path) -> None: ...     # {"instance_id": ..., "reason": "head_mismatch"}
def test_missing_checkout_is_skipped(tmp_path) -> None: ...  # reason "missing_checkout"
def test_failing_tests_are_never_passed(tmp_path, monkeypatch) -> None: ...  # task có FAIL_TO_PASS; spy build chỉ nhận (task_id, issue_text)
def test_main_writes_json(tmp_path) -> None: ...             # main([...]) trả 0, file output đọc được
```

- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Viết script: `validate_task`, `require_split(manifest, allowed=("dev","heldout") if allow_heldout else ("dev",))`, `git -C <dir> rev-parse HEAD` qua `subprocess.run` không shell, `PythonGraphBuilder(repo_key="trace/" + instance_id, repository_revision=base_commit)`, gold là `changed_source_files`.
- [ ] **Step 4:** Chạy → PASS.

---

### Task 5: Chạy thật và báo cáo

Môi trường WSL `~/.vgar-wsl` có Python 3.11.17 và pytest 8.4.2. Chạy WSL bằng file script trong scratchpad, không truyền `$VAR` qua `wsl.exe`.

- [ ] **Step 1:** Trong WSL, chép `src`, `tests`, `scripts` hiện tại sang `~/vgar-tr1-check`; với `PYTHONPATH=src`, chạy ba file test của TR-1 và `tests/test_task_graph.py` → PASS, giống Windows.
- [ ] **Step 2:** Tạo trong scratchpad manifest dev cho 16 task từ `tr1_tasks.json` (`repo` suy từ `instance_id`, `split` theo `split_of`, `changed_source_files` từ patch); tạo thư mục symlink tới các checkout trong `/home/nam/w10/repositories` và `w9/repositories`.
- [ ] **Step 3:** Chạy `scripts/measure_trace_links.py` theo từng lô dưới 10 phút. So với `tr1_results2.log`: 15 task không có traceback phải cho đúng các cạnh cũ; `psf__requests-1724` được phép khác và phải ghi rõ khác ở đâu; 18/33 frame có cạnh.
- [ ] **Step 4:** Ghi `docs/status/tv2_tr_1_trace_links_run_2026-11-10.md`: bảng như spec §1, nhóm traceback, số frame theo từng dòng bảng chọn đích, lệnh tái tạo.
- [ ] **Step 5:** Chạy suite `-m "not hf and not docker"` sau khi `source .superpowers/sdd/2026-11-08-tv2-layer1-remaining-facts/env.sh`. Expected: chỉ còn 3 test fail đã biết.
- [ ] **Step 6:** Đưa danh sách file và lệnh commit cho người dùng, kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
