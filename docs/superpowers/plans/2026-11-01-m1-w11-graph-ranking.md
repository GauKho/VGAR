# M1 W11: B10, B02, ranking hash, tune và đóng băng — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Graph sạch (B10, B02), ranking có hash, tune từng bước theo một luật viết trước, và config đóng băng bằng giá trị mặc định trong code. Đây là điểm bàn giao H2 và H3.

**Architecture:**
- B10 sửa `_resolve_symbol` trong builder. Nhãn resolver tách thành hằng `RESOLVER_PROFILE`, dùng chung cho `graph_version` và các script.
- Ranking có hàm `ranking_config_hash(config)`. Hash ghi vào diagnostics của retriever và vào record của `run_graph_retrieval.py`. Script nhận `--retrieval-config` để thử từng bước tune mà không sửa code.
- Mỗi bước tune được nhận hay bỏ bằng script so sánh ghép cặp (bootstrap có sẵn trong `compare.py`).
- Đóng băng: sửa giá trị mặc định của `RetrievalConfig` thành config thắng, rồi ghim hash trong test.

**Tech Stack:** Python 3.11, tree-sitter, pytest, FastMCP (`mcp.server.fastmcp`).

**Spec:**
- `docs/superpowers/specs/2026-10-31-w11-w12-parallel-split-design.md` §2 (W11), Phụ lục A (G1, G2, G6, S11), Phụ lục B (D1, D3, D4, D5, D8).
- Bổ sung đang chờ duyệt: `docs/m3_w11_decisions.md` E1, E2, E3, E4.

**Ngoài phạm vi:** **Incremental (M1-W11-1, G3–G5)** có plan riêng, viết sau brainstorm #4 (C1–C4). Lý do: chỉ mục tên duy nhất là toàn repo, nên link lại theo closure ngược không đủ để G3 pass, và hướng thiết kế chưa được chốt.

## Global Constraints

- CI: `python -m pytest -m "not hf and not docker"` phải xanh trước khi bàn giao mỗi PR.
- **Không** dùng `--allow-heldout`. Tune chỉ trên dev.
- `policy_hash` của A0–A2 không được đổi (D17, V11).
- Không commit `results/`, `artifacts/runs/`. **Người dùng tự commit:** mỗi task kết thúc bằng danh sách file và lệnh commit gợi ý, không chạy `git commit`.
- Nhánh `m1/w11-<việc>`. Mỗi PR khoảng 300 dòng diff trở xuống. Reviewer là M2.
- Lệnh build graph hoặc retrieval trên 25 repo là việc nặng (không dùng GPU): **hỏi người dùng trước khi chạy**.
- Tập tune và R1: `data/manifests/verified-c104f840cc67-dev-25.json` (xem Quyết định Q1).

## Quyết định đã chốt trong plan (người dùng duyệt khi review plan)

| ID | Quyết định | Lý do |
|---|---|---|
| A1 | B10 chỉ chặn fallback khi module được import **nằm ngoài repo** (`imported_module not in self.modules`). Module trong repo giữ fallback | Người dùng chọn ngày 01/11. Giữ được re-export qua `__init__.py` |
| Q1 (B1) | Tune và R1 dùng **dev-25 retrieval** `verified-c104f840cc67-dev-25.json`, không dùng tập ablation W10 | Manifest này có `gold_patch_path` và có sẵn run BM25 và graph W5–6. Manifest W10 không có gold. Hai tập chỉ trùng 5 task. Tune trên tập khác tập ablation còn giảm overfit cho A1–A3. Cả hai đều là split dev |
| Q2 (B2, E3) | Một bước được **nhận** khi chênh lệch trung bình `file_recall@5` > 0 **và** cận dưới CI95 bootstrap ghép cặp > 0 (seed 0, 2000 vòng, chỉ tính task `SUCCEEDED` ở cả hai run). Báo thêm `function_recall@5`, `file_mrr`, số task lợi và số task hại | Viết luật trước khi thấy số. Dùng lại `paired_stats` có sẵn |
| Q3 (B3) | Bước (b) chỉ thử `public_api_risk ∈ {0.05, 0.10}`. Các trọng số khác giữ nguyên, chuẩn hóa như code hiện có | Lưới nhỏ, cố định trước |
| Q4 (B4) | Bước (c) "giảm IMPORTS hop 2" **không làm trong retrieval**. Ghi vào `docs/m1_retrieval_method.md` là chuyển sang impact (RQ3, W12) | `RetrievalConfig` không có trọng số theo loại edge. Bằng chứng D3 đến từ `impact.py` |
| Q5 (B5, E4) | D5 gồm hai luật: **R1** — từ viết hoa đứng đầu câu, không có `_`, không có chữ hoa nào khác và không theo sau bởi `(` thì không tính là `code_like`. **R2** — token trong fenced block **không parse được thành Python** (log, traceback) thì không tính là `explicit`. Inline backtick vẫn là explicit | Đây là hai triệu chứng đã ghi ở W5–6. Task 5 kiểm lại trên pylint-4604 và pylint-6386 trước khi sửa |
| Q6 (C5) | Hash = `"sha256:" + sha256(json.dumps(asdict(config), sort_keys=True, separators=(",", ":")))` | E2 |

## Review Focus

1. **Relative import** `from .impl import helper` bên trong package có trong repo vẫn phải resolve sau B10 → Task 1, test G2c.
2. **Node id chứa `:` nhưng không chứa `/`**, gửi không encode, vẫn tìm thấy, và id chỉ được decode đúng một lần → Task 2, test S11b.
3. **Hash ổn định:** cùng nội dung `weights` nhưng thứ tự khóa khác thì hash phải trùng → Task 3, test G6b.
4. **Task fail hoặc timeout ở một trong hai run** (sympy từng timeout 300 giây) không được làm lệch phép so: chỉ ghép task `SUCCEEDED` ở cả hai run và báo `n` → Task 4, test T2.
5. **Class thật viết hoa đứng đầu câu** (ví dụ "Session objects…") vẫn phải được anchor, chỉ là điểm thấp hơn, không mất hẳn → Task 5, test D5c.

---

### Task 1: Hoàn tất B10 + E1 (đã code; còn hằng nhãn resolver, fixture, suite)

**Đã xong:**
- Sửa `src/vgar/graph/builder.py` `_resolve_symbol` và nhãn `v4-external-import`.
- Test G1, G2, G2b, G7 trong `tests/test_graph_builder.py`.

**Files:**
- Modify: `src/vgar/graph/builder.py` (thêm hằng `RESOLVER_PROFILE`, dùng ở `_calculate_graph_version`)
- Modify: `scripts/run_graph_retrieval.py:302`, `scripts/accept_m1_tokenizer.py:129` (import hằng)
- Modify: `docs/graph_schema.md:19`
- Regenerate: `tests/fixtures/w9_bundle/{task.json,bundle/*,fixture_profile.json}` bằng `scripts/build_w9_bundle_fixture.py`
- Test: `tests/test_graph_builder.py`

**Interfaces:**
- Produces: `vgar.graph.builder.RESOLVER_PROFILE: str = "tree-sitter+python-static-v4-external-import"`

- [ ] **Step 1: Viết test G2c (relative import trong package)**

```python
def test_relative_import_inside_repository_package_still_resolves(self) -> None:
    document = self._build_files({
        "src/pkg/__init__.py": "",
        "src/pkg/impl.py": "def helper():\n    return 1\n",
        "src/pkg/user.py": "from .impl import helper\n\ndef caller():\n    return helper()\n",
    })
    self.assertIn("pkg.impl.helper", self._call_targets(document))
```

- [ ] **Step 2: Chạy test.** `python -m pytest tests/test_graph_builder.py -q -k relative_import_inside`. Kỳ vọng: PASS. Đây là test chặn regression, pass ngay là đúng.
- [ ] **Step 3: Tách hằng `RESOLVER_PROFILE`** ở cấp module trong `builder.py` và dùng nó trong `_calculate_graph_version`. Thay chuỗi viết cứng ở hai script bằng `from vgar.graph.builder import RESOLVER_PROFILE`. Sửa câu ở `docs/graph_schema.md:19`.
- [x] **Step 4: Xem kết quả suite (đã chạy 01/11).** Kết quả: 1416 passed, 3 failed.
  - `tests/m2/w910/test_runner_contract.py::test_different_arm_contexts_can_share_template_without_same_prompt` và `tests/test_w9_bundle.py::test_checked_in_fixture_validates_and_matches_recipe`: do fixture `w9_bundle` → Step 5 xử lý.
  - `tests/test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory` (`resolved_count` 2 ≠ 3): **lỗi có từ trước**, vẫn fail khi gỡ thay đổi trong `builder.py`, nên không thuộc B10. Ghi vào mô tả PR, không sửa trong plan này.
- [ ] **Step 5: Dựng lại fixture.** Đọc `scripts/build_w9_bundle_fixture.py --help` để biết lệnh build. Build vào `tests/fixtures/w9_bundle`, rồi chạy `python -B scripts/build_w9_bundle_fixture.py --validate-root tests/fixtures/w9_bundle`. Kỳ vọng JSON có `status=PASS`. `git diff --stat tests/fixtures/w9_bundle` chỉ được đổi `graph_version` và các hash phụ thuộc; `repo/` và `repair-context.txt` không đổi.
- [ ] **Step 6: Kiểm V11.** Chạy `python -m pytest tests/m2 -q -k "policy_hash or golden"`. Kỳ vọng: PASS, và `policy_hash` A0–A2 không đổi.
- [ ] **Step 7: Chạy cả suite.** `python -m pytest -m "not hf and not docker" -q`. Kỳ vọng: chỉ còn 1 failed, là test `test_official_harness` có từ trước.
- [ ] **Step 8: Bàn giao.** Nhánh `m1/w11-b10`. Danh sách file: `builder.py`, `test_graph_builder.py`, 2 script, `docs/graph_schema.md`, `tests/fixtures/w9_bundle/**`. Mô tả PR ghi E1 là phần bổ sung chờ duyệt, và mời M2 review phần fixture.

### Task 2: B02 — decode node id đúng một lần ở resource

**Files:**
- Modify: `src/vgar/mcp/servers/graph_server.py` (`graph_node`, `graph_subgraph`)
- Test: `tests/test_w3_w4_graph_resources.py`

**Interfaces:**
- Produces: resource `vgar://graph/node/{node_id}` và `vgar://graph/subgraph/{node_id}` nhận node id đã được `urllib.parse.quote(id, safe="")`.

- [ ] **Step 1: Viết test S11 qua FastMCP thật**

```python
def test_node_resource_roundtrip_encoded_id(monkeypatch):
    from urllib.parse import quote
    import asyncio
    from vgar.mcp.servers import graph_server
    service = _sample_service()
    monkeypatch.setattr(graph_server, "graph_service", service)
    node_id = service.search_symbols("login", limit=1).symbols[0].symbol_id
    assert "/" in node_id and ":" in node_id
    contents = asyncio.run(graph_server.mcp.read_resource(f"vgar://graph/node/{quote(node_id, safe='')}"))
    assert json.loads(contents[0].content)["repo"]["node_id"] == node_id
```

  Thêm **S11b**: cùng cách gọi, nhưng với id không có `/` và không encode (ví dụ `vgar:x:python:function:a.py:f` lấy từ sample db nếu có, hoặc dùng `monkeypatch` cho `get_node` để ghi lại tham số). Kiểm `get_node` nhận đúng chuỗi gốc, không bị decode hai lần.
- [ ] **Step 2: Chạy test.** `python -m pytest tests/test_w3_w4_graph_resources.py -q -k roundtrip`. Kỳ vọng: S11 FAIL, ra `NodeNotFoundError` vì id vẫn còn dạng encode. Nếu FastMCP tự decode và test pass ngay thì dừng lại và báo người dùng: khi đó B02 nằm ở phía client chứ không phải server.
- [ ] **Step 3: Sửa.** Trong cả hai resource, gọi `node_id = urllib.parse.unquote(node_id)` đúng một lần, trước khi gọi `_resource` và `graph_service`. Audit ghi id đã decode.
- [ ] **Step 4: Chạy lại.** File test resource cộng `tests/test_mcp_tool_contract.py`. Kỳ vọng: PASS.
- [ ] **Step 5: Bàn giao.** Nhánh `m1/w11-b02`. Phải merge **trước hết W11 ngày 2**, vì sau đó `graph_server.py` thuộc M3.

### Task 3: Hash config ranking (G6) và cờ `--retrieval-config`

**Files:**
- Modify: `src/vgar/graph/retrieval.py` (hàm hash; diagnostics; cờ `public_api_risk_is_default_rank_signal` tính từ trọng số thay vì viết cứng `False`)
- Modify: `scripts/run_graph_retrieval.py` (thêm `--retrieval-config PATH`; ghi `ranking_config_hash` vào `config.retrieval`; dùng cùng một `RetrievalConfig` ở dòng 104 và 296)
- Test: `tests/test_graph_retrieval.py`

**Interfaces:**
- Produces: `vgar.graph.retrieval.ranking_config_hash(config: RetrievalConfig) -> str`, có dạng `"sha256:<64 hex>"`.
- Produces: `RetrievalResult.diagnostics["ranking_config_hash"]`.
- Produces: file JSON cho `--retrieval-config` gồm các field của `RetrievalConfig`, ví dụ `{"weights": {...}}`. Field không có trong file thì lấy giá trị mặc định.

- [ ] **Step 1: Viết test**
  - **G6:** `ranking_config_hash(RetrievalConfig())` khác `ranking_config_hash(RetrievalConfig(weights={**default, "public_api_risk": 0.1}))`. Diagnostics của một lần `retrieve` trên graph fixture chứa đúng `ranking_config_hash(retriever.config)`.
  - **G6b:** `weights` có cùng nội dung nhưng khác thứ tự khóa thì ra cùng hash.
- [ ] **Step 2: Chạy test.** `python -m pytest tests/test_graph_retrieval.py -q -k hash`. Kỳ vọng: FAIL, `ImportError: ranking_config_hash`.
- [ ] **Step 3: Implement** theo công thức Q6. Thêm khóa vào `diagnostics`. Đổi `"public_api_risk_is_default_rank_signal"` thành `self.config.weights["public_api_risk"] > 0`.
- [ ] **Step 4: Thêm `--retrieval-config`** vào `run_graph_retrieval.py`. Thêm test CLI nhỏ cho hàm parse, nếu script có hàm tách riêng được. Nếu không, kiểm tay bằng `--limit 1 --offline` (bước nhẹ, không cần hỏi).
- [ ] **Step 5: Chạy cả suite.** Kỳ vọng: 0 failed.
- [ ] **Step 6: Bàn giao.** Nhánh `m1/w11-ranking-hash`.

### Task 4: Luật nhận bước tune (E3), script so bước, sửa doc

**Files:**
- Create: `scripts/compare_tune_steps.py`
- Modify: `src/vgar/evaluation/retrieval/compare.py` (thêm `compare_graph_runs`, dùng lại `_task` và `paired_stats`)
- Modify: `docs/m1_retrieval_method.md` (sửa bảng trọng số ở dòng 147–154 cho khớp code; thêm mục "Giao thức tune W11" chép nguyên Q1–Q5)
- Test: `tests/test_retrieval_compare.py` (tạo mới nếu chưa có file test cho `compare.py`)

**Interfaces:**
- Consumes: hai thư mục run `results/retrieval/<run>/` do `run_graph_retrieval.py` tạo, có `result.json` và `tasks/`.
- Produces: `compare_graph_runs(previous: Path, candidate: Path, arm: str = "graph", metric: str = "file_recall@5", seed: int = 0) -> dict`, gồm các khóa `{"n", "mean_delta", "ci95", "wins", "losses", "verdict": "ACCEPT" | "REJECT", "previous_hash", "candidate_hash"}`.

- [ ] **Step 1: Viết test trên per-task dict tổng hợp** (không cần chạy retrieval thật)
  - **T1:** chênh lệch luôn dương trên 10 task → `ACCEPT`.
  - **T2:** một task `FAILED` ở run sau thì bị loại khỏi phép ghép, `n == 9`.
  - **T3:** chênh lệch có dấu trộn lẫn, trung bình gần 0 → `REJECT`.
  - **T4:** hai run khác `manifest_hash` → `ValueError`.
- [ ] **Step 2: Chạy test.** Kỳ vọng: FAIL, chưa có hàm.
- [ ] **Step 3: Implement** `compare_graph_runs` và CLI mỏng `scripts/compare_tune_steps.py PREV CAND [--metric] [--seed]`. CLI in JSON và exit 0.
- [ ] **Step 4: Chạy test.** Kỳ vọng: PASS. Sau đó chạy cả suite.
- [ ] **Step 5: Sửa doc.** Viết giao thức tune vào `m1_retrieval_method.md` **trước** Task 6. Ghi luôn Q4 (bước (c) chuyển sang RQ3).
- [ ] **Step 6: Bàn giao.** Nhánh `m1/w11-tune-protocol`.

### Task 5: D5 — sửa anchor nhiễu ở `grounding.py`

**Files:**
- Modify: `src/vgar/graph/grounding.py:363-389`
- Test: `tests/test_graph_grounding.py` (hoặc file test grounding hiện có; tìm bằng `grep -l find_task_anchors tests`)

- [ ] **Step 1: Kiểm giả thuyết trước khi viết test.** Chạy `find_task_anchors` trên issue của `pylint-dev__pylint-4604` và `pylint-dev__pylint-6386` (lấy từ dev-25 manifest, graph build qua `run_graph_retrieval.py --limit` hoặc builder trực tiếp; **hỏi người dùng** nếu phải build repo lớn). Ghi ra các anchor có điểm ≥ 0,6 nhưng không nằm trong gold. Nếu nguồn nhiễu **không phải** R1 hoặc R2 thì dừng lại và báo người dùng, không đoán luật mới.
- [ ] **Step 2: Viết test**
  - **D5a (R1):** issue "When the option is set, the checker crashes." Graph có hàm `When` → anchor `When` có điểm ≤ 0,4.
  - **D5b (R2):** issue có fenced block là traceback hoặc log, không parse được thành Python, chứa token `Checker` → token đó không có điểm explicit 0,75.
  - **D5c (Review Focus 5):** "Session objects leak connections." Graph có class `Session` → `Session` vẫn có trong anchors với điểm > 0.
  - **D5d:** inline `` `Checker` `` vẫn là explicit, điểm 0,75.
  - Thêm 1 test hồi quy dựng từ đúng đoạn văn bản gây nhiễu tìm được ở Step 1.
- [ ] **Step 3: Chạy test.** Kỳ vọng: D5a, D5b FAIL; D5c, D5d PASS.
- [ ] **Step 4: Implement.**
  - R1: thêm điều kiện "đầu câu" (token ở đầu văn bản, hoặc đứng sau `.`, `!`, `?` cộng khoảng trắng hay xuống dòng) vào cách tính `code_like`.
  - R2: `code_spans` chỉ tính fence nào parse được bằng `ast.parse`. `_code_scopes` đã thử parse ở dòng 104–111, nên dùng lại kết quả đó.
- [ ] **Step 5: Chạy test grounding và cả suite.** Kỳ vọng: PASS.
- [ ] **Step 6: Bàn giao.** Nhánh `m1/w11-anchor-noise`.

### Task 6: Chạy các bước tune trên dev-25 và ghi bảng R1 (thực nghiệm, không thêm code)

**Consumes:**
- Step 1 cần Task 1–4.
- Step 2 trở đi cần thêm Task 5.

**Thứ tự thực hiện:** chạy Step 1 **trước khi** làm Task 5, để dòng "trước tune" không có D5.

Mỗi lệnh chạy 25 task là việc nặng: **hỏi người dùng trước**, rồi chạy nền. Lệnh mẫu:

```
python scripts/run_graph_retrieval.py . data/manifests/verified-c104f840cc67-dev-25.json \
  --tokenizer-manifest artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json \
  --budget-tokens 8000 --rebuild-graphs --cache-graphs [--retrieval-config <file>]
```

- [ ] **Step 1: Bước (a), trước tune.** Code sau Task 1–4, trọng số cũ, chưa có D5. Đây là dòng R1 "graph trước tune". Có `--rebuild-graphs` vì `graph_version` đã đổi.
- [ ] **Step 2: Bước (d), D5.** Chạy với code đã có Task 5. So với (a) bằng `compare_tune_steps.py`. Ghi verdict.
- [ ] **Step 3: Bước (b).** Hai file `--retrieval-config`, với `public_api_risk` lần lượt 0,05 và 0,10. So mỗi file với bước được nhận gần nhất. Nếu cả hai cùng `ACCEPT` thì chọn file có `mean_delta` lớn hơn.
- [ ] **Step 4: Ghi bảng R1** vào `docs/m1_retrieval_method.md`. Mỗi bước một dòng: `ranking_config_hash`, `graph_version` profile, N, các cột của R1 và verdict. Dòng BM25 lấy từ run BM25 W5–6 đã có trong `results/retrieval/` (ghi run id). Nếu sympy timeout thì ghi rõ `n`.
- [ ] **Step 5: Bàn giao.** Đường dẫn các run ghi vào `docs/status/m1.md`. Không commit `results/`.

### Task 7: Đóng băng config (E2) → H3

**Files:**
- Modify: `src/vgar/graph/retrieval.py:29-30` (`_WEIGHTS` và các field mặc định, đặt bằng config thắng ở Task 6)
- Modify: `tests/test_graph_retrieval.py` (thêm `FROZEN_RANKING_HASH`)
- Modify: `docs/m1_retrieval_method.md` (ghi hash đóng băng)

- [ ] **Step 1: Viết test G6c:** `assert ranking_config_hash(RetrievalConfig()) == FROZEN_RANKING_HASH`, với giá trị là hash của config thắng ở Task 6.
- [ ] **Step 2: Chạy test.** Kỳ vọng: FAIL nếu config thắng khác mặc định; PASS nếu không bước nào được nhận. Trường hợp thứ hai vẫn hợp lệ: ghi "giữ trọng số cũ trên graph sau B10".
- [ ] **Step 3: Sửa giá trị mặc định** cho khớp config thắng.
- [ ] **Step 4: Chạy cả suite.** Kỳ vọng: 0 failed. Nếu test M2 có ghim prompt hoặc context thì báo lại, vì context của fixture có thể đổi.
- [ ] **Step 5: Bàn giao H3.** Nhánh `m1/w11-ranking-freeze`. Ghi hash vào `docs/m1_retrieval_method.md`, và báo M3 (chính bạn) để chạy E5 so 60 ô.
