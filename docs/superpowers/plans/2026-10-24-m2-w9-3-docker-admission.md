# M2-W9-3 Docker admission implementation plan

> Use superpowers:executing-plans inline; one fresh final reviewer. No commits.

**Goal:** A manifest pilot reaches the full run_repair lifecycle without the trusted fixture registry; altered hashes are rejected.
**Spec:** D:/Project/CAPSTONES/New_task/VGAR_W9_W16_Deliverables.md, M2-W9-3; docs/repair_runner_interface.md section 6; M1-W9-5 profile.
**Architecture:** Opt-in docker_admitted runtime. Pin manifest/profile and handoff hashes independently; compare original bytes against exact Git tree and qualified Python inventory. Keep Git/patches in private host lease. Every target command uses a fresh isolated digest-pinned Docker container and copies a verified private snapshot without mounts. Persist admission alongside experiment metadata, validate before load/save and execution. Existing native fixture gate stays intact.
**Constraints:** Preserve all previous dirty work, HEAD/index, registry and canonical five tasks/profiles. No model, gold, held-out, dependency install, cache release, Docker settings/reset/prune, commit/push, Task Status.md or subsequent tasks. Bounded commands, cleanup evidence and no live owned containers.
**Rulings:** Continue user-selected Docker-only and no design-review loop. D4 uses independent issue reproduction (not F2P/P2P/test_patch); overlay pinned and protected. D6 uses all production Python files under caller-declared source roots, excluding test directories, with no gold-derived path selection. Smoke uses scripted generation, A0 with explicit arm, smaller fresh context and fixture-only counter: no claim of real model/retrieval performance. Existing profiles marked EXCLUDED remain rejected. Work in user-selected dirty checkout, no worktree/index/branch changes. Evidence/ledger retained.

## Task 1: Admission and persisted lifecycle
Files: new src/vgar/repair/admission.py; modify contracts.py, pipeline.py, session.py, workspace.py, verification.py; tests/m2/w910/test_admission.py.
- [x] RED: test independent manifest/profile hashes, task/repo/base/issue mismatch, exact source/tree and bundle pins, rejected EXCLUDED, protected source-root/overlay rules, immutable source and legacy gate.
- [x] Implement admit_task and validate_admission, source inventory from Git tree, opt-in runtime and session/record binding before load_run, private overlay with execution-before inventory and attribute-safe private Git snapshot.
- [x] GREEN: focused admission/session tests including removal/tampering, source preservation and legacy fixtures.

## Task 2: Docker command bridge
Files: new src/vgar/repair/docker_executor.py and docker_probe.py; modify static_checks.py; new tests/m2/w910/test_docker_admission.py.
- [x] RED: approved argv/path mapping, exact private bytes attestation, target interpreter/syntax, reports copied back, timeout/truncation/cleanup fail closed, no native test fallback or arbitrary executable.
- [x] Implement fixed Docker CLI adapter; unique label/name; daemon/image identity; no network/mounts; reset base only before loading candidate. Target stdlib probe validates base Python inventory, extracts only safe regular snapshot files, attests before/after, captures syntax/pytest report and runtime identity. Host bounded processes and finally ownership-verified cleanup.
- [x] GREEN: focused fake transport and target-side tests, plus meaningful selected regressions.

## Task 3: Real pilot and delivery
Files: evidence-only smoke recipe/run and docs/m2_w9_3_admission.md, docs/status/m2.md, docs/m2_w9_decisions.md, docs/repair_runner_interface.md, PROGRESS.md; final review doc.
- [x] Qualify existing runtime/resources without modifying environment. Use xarray issue reproduction from problem_statement with immutable existing COLLECTED profile, unchanged original source and no gold. Scripted candidate only in private lease.
- [x] Run real Docker-backed run_repair; save full terminal record, baseline/post node outcomes, target identity/snapshot and cleanup. Negative hash tests must reject before Docker; no trusted registry mutation.
- [x] Run full W78/W9 gate and scoped lint; inspect outputs. One fresh final code review; Important fixes get RED/GREEN and green regression.
- [x] Update status/decisions/interface/PROGRESS and final preservation checkpoint; no extra tasks or commits.

## Review focus
- Hash-valid self-supplied inputs need external expected pins; no claim of authentication.
- Source/config/test drift and links must be rejected before execution.
- Lost runtime metadata on resume must fail closed.
- Deadline kills Docker CLI and finally destroys owned target container; cleanup failure prevents success.
- Optional unavailable static tools must stay recorded ERROR; A2 cannot qualify without them.