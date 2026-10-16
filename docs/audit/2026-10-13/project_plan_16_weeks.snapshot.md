# VGAR-MCP — Kế hoạch đồ án 16 tuần

> **Mục tiêu:** Xây dựng và đánh giá VGAR-MCP cho multi-file software repair: graph-guided retrieval, patch-impact analysis, verification evidence, và tích hợp qua MCP/LangChain.
>
> **Scope MVP:** Python + SWE-bench Verified/Lite + một mô hình cố định + graph MVP (Layer 1, 2, 5, 6).

## Vai trò thành viên

| Thành viên | Vai trò chính | Ownership |
|---|---|---|
| **M1** | Graph & Retrieval Owner | Graph schema, parsing, symbol resolution, task grounding, graph retrieval, impact graph, incremental update |
| **M2** | Repair & Verification Owner | Repair pipeline, patch application, test/type/lint checks, evidence bundle, API/structural verification |
| **M3** | MCP, Evaluation & Paper Owner | MCP server, LangChain integration, benchmark orchestration, statistics, artifact, paper/submission |

## Quy ước chung

- Mọi experiment phải lưu: task id, commit/revision, model, prompt version, temperature, token budget, timeout, tool calls, diff, test output và evidence.
- Không đổi benchmark split, model, prompt budget hoặc metric sau khi đã chốt held-out evaluation nếu không ghi rõ lý do.
- Patch chỉ được áp dụng vào worktree/sandbox; không ghi vào repository gốc trong evaluation.
- Mỗi tuần có một buổi đồng bộ 60–90 phút và một PR review chéo.

## Kiến trúc mục tiêu

```text
User / SWE-bench issue
  -> LangChain App / Agent
  -> langchain-mcp-adapters
  -> VGAR-MCP Server
  -> Layer 1: syntax extraction (tree-sitter)
  -> Layer 2: symbol/reference enrichment (SCIP/LSP/Pyright)
  -> Layer 3: optional deep static analysis (Joern/CodeQL)
  -> Layer 4: optional GraphDiff/history cleaning
  -> Layer 5: tests/typecheck/lint/invariant evidence
  -> Layer 6: graph store + MCP resources/tools
  -> Repository sandbox/worktree
```

## Milestone tổng quan

| Mốc | Thời gian | Kết quả bắt buộc |
|---|---:|---|
| M1 | Tuần 1–2 | Research protocol, graph schema, benchmark/model scope |
| M2 | Tuần 3–4 | Graph MVP + MCP/LangChain connectivity |
| M3 | Tuần 5–6 | Task grounding + graph retrieval + BM25 baseline |
| M4 | Tuần 7–8 | Repair loop + verification cơ bản |
| M5 | Tuần 9–10 | Impact analysis + ablation sơ bộ |
| M6 | Tuần 11–12 | MCP hoàn chỉnh + performance/security tối thiểu |
| M7 | Tuần 13–14 | Held-out evaluation + failure analysis |
| M8 | Tuần 15–16 | Paper + public artifact + submission |

---

# Tuần 1–2 — Research design và kiến trúc

## Mục tiêu chung

- [ ] Chốt claim nghiên cứu: **graph-guided retrieval + verification evidence cho multi-file repair**.
- [ ] Chốt scope: Python, SWE-bench Verified hoặc Lite, một model cố định.
- [ ] Chốt model version, temperature, token budget, timeout, max iterations và max tool calls.
- [ ] Chốt graph MVP: node/edge nào bắt buộc, layer nào optional.
- [ ] Tạo repository chung, issue board, branching/PR convention và cấu trúc source code.
- [ ] Viết protocol thực nghiệm nội bộ trước khi chạy benchmark chính.

## M1 — Graph & Retrieval

- [ ] Đọc/tóm tắt 8–10 bài về CPG, repository graph, graph retrieval, code localization.
- [ ] Viết `docs/graph_schema.md`: node types, edge types, properties, confidence/provenance.
- [ ] Chốt schema MVP: `File`, `Module`, `Class`, `Function`, `Method`, `Import`, `CallSite`, `Test`, `Issue`.
- [ ] Chốt edges MVP: `CONTAINS`, `IMPORTS`, `CALLS`, `REFERENCES`, `TESTS`, `MENTIONS`, `REPRODUCES`.

**Deliverable:** `docs/graph_schema.md`.

## M2 — Repair & Verification

- [ ] Đọc/tóm tắt 8–10 bài về APR, LLM repair, plausible patches, validation/overfitting.
- [ ] Viết `docs/verification_design.md`.
- [ ] Chốt lớp verification MVP: failing/relevant tests, typecheck, lint, API signature check cơ bản.
- [ ] Thiết kế JSON schema cho evidence bundle.

**Deliverable:** `docs/verification_design.md` và `docs/evidence_bundle_schema.md`.

## M3 — MCP, Evaluation & Paper

- [ ] Đọc/tóm tắt 8–10 bài về SWE-bench, Agentless, MCP/tool use/security.
- [ ] Viết `docs/research_design.md`: RQ, hypothesis, benchmark, split, baselines, metrics, fairness protocol.
- [ ] Tạo literature-review table 30–50 papers.
- [ ] Cài thử MCP SDK, `langchain-mcp-adapters`, SWE-bench tooling.

**Deliverable:** `docs/research_design.md`, `docs/literature_review.csv`.

## Definition of Done

- [ ] Cả nhóm ký xác nhận scope và protocol.
- [ ] Có branch protection/PR review.
- [ ] Literature table có tối thiểu 20 bài đã điền.

---

# Tuần 3–4 — Graph MVP (Layer 1, 2, 6)

## Mục tiêu chung

- [ ] Xây graph cho repository Python.
- [ ] MCP server và LangChain client kết nối được.
- [ ] Có tests trên repo nhỏ trước khi chạy SWE-bench.

## M1 — Graph & Retrieval

- [ ] Tích hợp tree-sitter Python.
- [ ] Parse `.py` files và extract: file/module/class/function/method/import/callsite.
- [ ] Build graph nodes/edges cơ bản.
- [ ] Tích hợp symbol resolution tối thiểu bằng SCIP/LSP/Pyright/Jedi.
- [ ] Resolve import và một số direct call điển hình; lưu `confidence` và `provenance`.
- [ ] Lưu graph vào SQLite hoặc Kùzu.
- [ ] Viết unit tests cho parser, extractor và graph query.

**Deliverable:** graph builder chạy trên 1–2 repo Python mẫu; unit tests pass.

## M2 — Repair & Verification

- [ ] Thiết lập sandbox/worktree để chạy patch an toàn.
- [ ] Viết test runner wrapper cho pytest.
- [ ] Thu thập test result baseline: command, stdout/stderr, exit code, duration.
- [ ] Hoàn thiện schema evidence bundle và writer JSON.

**Deliverable:** `run_tests` wrapper và baseline evidence JSON.

## M3 — MCP, Evaluation & Paper

- [ ] Tạo MCP server tối thiểu.
- [ ] Resources: `vgar://repo/summary`, `vgar://graph/node/{id}`, `vgar://graph/subgraph/{id}`.
- [ ] Tools: `search_symbols`, `get_callers`, `get_callees`.
- [ ] Tạo LangChain client dùng `langchain-mcp-adapters` hoặc MCP client tương đương.
- [ ] Ghi audit log cơ bản cho tool calls.

**Deliverable:** LangChain client gọi được ít nhất 3 MCP tools trên repo mẫu.

## Definition of Done

- [ ] Query callers/callees/imports trả kết quả hợp lý.
- [ ] Có manual validation ít nhất 20 call/import edges.
- [ ] Có dashboard/log hoặc file kết quả thể hiện số node, edge, build time.

---

# Tuần 5–6 — Task grounding và graph retrieval

## Mục tiêu chung

- [ ] Issue/failing test được nối với graph.
- [ ] Có graph-guided context retrieval dưới token budget.
- [ ] Có BM25 baseline và evaluation retrieval sơ bộ.

## M1 — Graph & Retrieval

- [ ] Implement `find_task_anchors(issue_text, failing_tests)`.
- [ ] Extract file path, symbol mention, stack trace frame, failing test, route/API mention.
- [ ] Tạo `Issue`/`FailingTest` nodes và trace edges.
- [ ] Implement `get_related_context(anchor_ids, budget_tokens)`.
- [ ] Traverse k-hop neighbors, callers, callees, tests, dependents.
- [ ] Rank candidates theo graph distance, confidence, failing-test proximity, public API risk.
- [ ] Pack snippets dưới token budget.

**Deliverable:** task grounding + graph retrieval API chạy được.

## M2 — Repair & Verification

- [ ] Implement BM25 baseline trên function/code chunks.
- [ ] Chuẩn hóa gold-file/gold-function extraction từ developer patch.
- [ ] Chạy retrieval evaluation ban đầu trên 20–30 SWE-bench tasks.
- [ ] Phối hợp M1 debug context format và gold-label mapping.

**Deliverable:** BM25 baseline và script đo Recall@k.

## M3 — MCP, Evaluation & Paper

- [ ] Thêm MCP tools: `find_task_anchors`, `get_related_context`.
- [ ] LangChain flow: issue -> anchors -> context -> print/display context.
- [ ] Chuẩn bị SWE-bench subset 50–100 task có environment chạy được.
- [ ] Viết draft Related Work: graph representation và graph-guided retrieval.

**Deliverable:** SWE-bench manifest + draft Related Work phần graph/retrieval.

## Definition of Done

- [ ] Có bảng `Graph vs BM25` với Recall@3, Recall@5, Recall@10 và token cost.
- [ ] Có ít nhất 10 task được manual-inspect để xác nhận retrieval hợp lý.

---

# Tuần 7–8 — Repair pipeline và verification cơ bản

## Mục tiêu chung

- [ ] Agent tạo được unified diff từ issue + retrieved context.
- [ ] Patch được áp dụng trong worktree.
- [ ] Có tests/type/lint evidence.

## M1 — Graph & Retrieval

- [ ] Chuẩn hóa payload context: code snippets, node ids, paths, metadata, relevance score.
- [ ] Cải thiện ranking trên development subset; ghi rõ mọi heuristic/tuning.
- [ ] Thêm test-to-function links nếu có thể suy ra từ naming/path/coverage.

**Deliverable:** context payload versioned và retrieval report.

## M2 — Repair & Verification

- [ ] Xây repair prompt template cố định.
- [ ] Tích hợp một LLM backend cố định (HF/Codex/Claude theo protocol).
- [ ] Validate/parse unified diff.
- [ ] Implement `apply_patch` vào temporary worktree.
- [ ] Implement relevant-test selection cơ bản.
- [ ] Chạy pytest, typecheck và lint.
- [ ] Tạo evidence bundle với: patch applied, failing-test result, relevant-test result, typecheck, lint.

**Deliverable:** pipeline issue -> context -> diff -> worktree -> evidence bundle.

## M3 — MCP, Evaluation & Paper

- [ ] Expose MCP tools: `apply_patch`, `run_relevant_tests`, `verify_patch` bản cơ bản.
- [ ] LangChain loop một vòng: retrieve -> generate -> patch -> verify.
- [ ] Log prompt version, model configuration, tool calls, latency, token usage.
- [ ] Viết draft Methodology: system overview, graph construction, retrieval.

**Deliverable:** demo end-to-end cho 3–5 task nhỏ.

## Definition of Done

- [ ] Có ít nhất 3 task sinh được diff hợp lệ và chạy được verification.
- [ ] Không ghi trực tiếp vào repo gốc.

---

# Tuần 9–10 — Impact analysis và ablation sơ bộ

## Mục tiêu chung

- [ ] Map diff sang graph nodes.
- [ ] Có impact report.
- [ ] Chạy A0–A2 trên subset đủ lớn.

## M1 — Graph & Retrieval

- [ ] Implement diff-to-node mapping: file/range/symbol -> graph node.
- [ ] Implement impact traversal: reverse `CALLS`, `IMPORTS`, `TESTS`, component dependencies.
- [ ] Tính risk features: changed public API, fan-in, affected callers/tests/components.
- [ ] Viết impact report JSON.

**Deliverable:** `analyze_patch_impact` module.

## M2 — Repair & Verification

- [ ] Implement variants:
  - [ ] **A0:** BM25 + tests only.
  - [ ] **A1:** Graph retrieval + tests only.
  - [ ] **A2:** Graph retrieval + tests + typecheck/lint.
- [ ] Chạy trên 30–50 development tasks.
- [ ] Đo patch success, false accept proxy, token/task, latency/task.
- [ ] Ghi failure reason có cấu trúc.

**Deliverable:** ablation script và bảng kết quả sơ bộ.

## M3 — MCP, Evaluation & Paper

- [ ] Expose `analyze_patch_impact` qua MCP.
- [ ] Tích hợp impact report vào LangChain feedback prompt.
- [ ] Viết draft Methodology: repair, impact analysis, verification.
- [ ] Viết draft Experimental Design: datasets, split, baselines, metrics, fairness controls.

**Deliverable:** Methodology/Experimental Design draft v1.

## Definition of Done

- [ ] A0–A2 chạy end-to-end bằng cùng benchmark subset và configuration.
- [ ] Có ít nhất 1 bảng kết quả, không chỉ demo case.

---

# Tuần 11–12 — MCP hoàn chỉnh, security và performance

## Mục tiêu chung

- [ ] Hoàn thiện MCP tool surface cần thiết.
- [ ] Có security guardrails tối thiểu.
- [ ] Đo performance và incremental update.

## M1 — Graph & Retrieval

- [ ] Implement incremental graph update cho changed files.
- [ ] Reparse changed files, relink affected symbols, invalidate cache.
- [ ] Đo cold build time, warm update time, affected node count, cache hit rate.

**Deliverable:** incremental-update benchmark report.

## M2 — Repair & Verification

- [ ] Thêm API compatibility checks: exported function/class, signature change cơ bản.
- [ ] Thêm structural checks: forbidden import/layer rule/cycle rule nếu repo configuration cho phép.
- [ ] Implement **A3:** graph retrieval + verification graph/API checks.
- [ ] Đo false accept/false reject trên patch pool hoặc synthetic mutations nếu khả thi.

**Deliverable:** verification v2 + A3 results.

## M3 — MCP, Evaluation & Paper

- [ ] Hoàn thiện MCP server tool schemas và error responses.
- [ ] Security tối thiểu: path allowlist/jail, read-only by default, command allowlist, timeout, audit log.
- [ ] Đo latency/tool call, token/task, tool calls/task, read redundancy.
- [ ] Viết draft Results với retrieval, repair, verification, efficiency tables.

**Deliverable:** MCP/security checklist và Results draft v1.

## Definition of Done

- [ ] MCP tools không chạy command tùy ý.
- [ ] Có số liệu cold vs warm graph update và MCP overhead.

---

# Tuần 13–14 — Held-out evaluation và failure analysis

## Mục tiêu chung

- [ ] Dừng tuning heuristic trên development set.
- [ ] Chạy held-out evaluation đã chốt trước.
- [ ] Phân tích failure có hệ thống.

## M1 — Graph & Retrieval

- [ ] Chạy retrieval trên held-out set.
- [ ] Báo cáo gold-file/function Recall@k, MRR, token cost.
- [ ] Phân tầng single-file/multi-file.
- [ ] Phân tích 10–15 retrieval failures.

**Deliverable:** final retrieval table + failure taxonomy.

## M2 — Repair & Verification

- [ ] Chạy A0–A3 trên held-out set.
- [ ] Báo cáo resolved rate, multi-file resolved rate, false accept/reject, relevant-test coverage.
- [ ] Phân tích 10–15 repair/verification failures.

**Deliverable:** final repair/verification table + failure taxonomy.

## M3 — MCP, Evaluation & Paper

- [ ] Tính mean/median/std hoặc confidence interval.
- [ ] Làm paired comparison khi cùng task được so sánh giữa variants.
- [ ] Hoàn thiện plots/tables có caption và configuration note.
- [ ] Viết Threats to Validity: construct, internal, external, reliability/security.

**Deliverable:** analysis notebook/script + paper draft gần hoàn chỉnh.

## Definition of Done

- [ ] Mọi con số trong paper có script tái tạo.
- [ ] Không thay đổi protocol sau khi thấy held-out results.

---

# Tuần 15–16 — Paper, artifact và submission

## Mục tiêu chung

- [ ] Đóng gói artifact tái lập được.
- [ ] Viết paper theo evidence, không theo lời hứa.
- [ ] Review chéo và chuẩn bị submission.

## M1 — Graph & Retrieval

- [ ] Hoàn thiện Methodology: graph schema, graph construction, task grounding, retrieval.
- [ ] Kiểm tra code graph builder, schema migration, unit tests.
- [ ] Viết README cho graph/retrieval modules.

**Deliverable:** methodology section graph/retrieval + artifact-ready module.

## M2 — Repair & Verification

- [ ] Hoàn thiện Methodology: repair loop, patch impact, verification evidence.
- [ ] Kiểm tra sandbox/worktree cleanup, test runner, verification report.
- [ ] Viết README cho repair/verification modules.

**Deliverable:** methodology section repair/verification + artifact-ready module.

## M3 — MCP, Evaluation & Paper

- [ ] Hoàn thiện Introduction, Abstract, Conclusion, Results, Threats to Validity.
- [ ] Chuẩn bị Dockerfile/Dev Container, install scripts, benchmark manifest, reproducibility script.
- [ ] Nhờ ít nhất một người ngoài nhóm chạy theo README.
- [ ] Chọn venue và kiểm tra formatting, ethics, artifact policy, authorship requirements.

**Deliverable:** paper final + public/private artifact release + submission package.

## Definition of Done

- [ ] `README` từ máy sạch có thể chạy demo và tái tạo ít nhất một bảng kết quả.
- [ ] Paper không overclaim; mọi claim chính có bảng/figure/evidence tương ứng.
- [ ] Có issue list cho các limitations và future work.

---

# Bảng ablation tối thiểu

| Variant | Retrieval | Verification | Mục tiêu |
|---|---|---|---|
| A0 | BM25 | Tests only | Baseline text retrieval |
| A1 | Graph retrieval | Tests only | Giá trị của graph retrieval |
| A2 | Graph retrieval | Tests + typecheck + lint | Giá trị của evidence cơ bản |
| A3 | Graph retrieval | A2 + API/structural graph checks | Giá trị của graph verification |
| A4 (tuỳ chọn) | Graph + task/architecture enhancements | A3 + semantic invariants | Full research extension |
| A5 (tuỳ chọn) | A4 served through full MCP agent workflow | A4 | MCP usability/demo extension |

# Metrics tối thiểu

| Nhóm | Metrics |
|---|---|
| Retrieval | Gold-file Recall@3/5/10, gold-function Recall@k, MRR, context token cost |
| Repair | Resolved rate, multi-file resolved rate, iterations, latency/task, token/task |
| Verification | False accept, false reject, API-break detection, structural-violation detection |
| Graph quality | Symbol/call edge precision-recall trên manual sample, graph build/update time |
| MCP usability | Tool calls/task, tool latency, invalid call rate, audit-log completeness |

# Phân công giao diện giữa các thành viên

| Interface | Owner tạo | Owner dùng | Hợp đồng tối thiểu |
|---|---|---|---|
| Graph schema & node IDs | M1 | M2, M3 | Stable node id, type, path/range, confidence, provenance |
| Context payload | M1 | M2, M3 | snippets, token count, relevance, graph rationale, anchor ids |
| Patch/evidence payload | M2 | M3 | diff, worktree id, test result, checks, recommendation, reasons |
| MCP tool schemas | M3 | M1, M2 | typed arguments, stable return schema, error codes, audit metadata |
| Evaluation manifest | M3 | M1, M2 | task id, repo revision, split, commands, expected oracle metadata |

# Họp và quản trị tiến độ

- **Daily async:** mỗi người cập nhật: hôm qua làm gì, hôm nay làm gì, blocker gì.
- **Weekly sync:** demo trực tiếp một capability mới; review milestone checklist.
- **PR review:** ít nhất một thành viên khác review trước khi merge vào main.
- **Experiment review:** không merge kết quả vào paper nếu thiếu config, log, seed/model version hoặc script tái tạo.
- **Risk review tuần 6, 10, 12:** nếu một module chưa ổn, cắt scope optional trước khi ảnh hưởng core evaluation.

# Quy tắc cắt scope nếu chậm tiến độ

1. Giữ bằng mọi giá: Layer 1 + Layer 2 + Layer 6, graph retrieval, BM25 baseline, repair loop, tests-only verification, evaluation scripts.
2. Chỉ làm khi core đã chạy: type/lint, API checks, impact analysis, incremental update, LangChain UI/demo.
3. Để extension/future work nếu thiếu thời gian: Layer 3 full CPG, Layer 4 GraphDiff, architecture lift tự động, Daikon invariants, fine-tuning, multi-language support.
