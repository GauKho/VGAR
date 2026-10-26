# M1-W9-5 Docker-only task environments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. User explicitly selected inline Docker-only execution and opted out of design questions/approval.

**Goal:** prepare immutable environment profiles and actual base-commit pytest collection records for all five fixed W9 pilot tasks, with evidenced exclusions.
**Architecture:** new host task_env module validates immutable inputs/profiles and owns fresh Docker containers; a small stdlib/pytest probe runs under target Python without installing VGAR. Reuse official.py process capture/ownership cleanup, not gold execution. Entry script defaults to preflight; explicit execute required for collection.
**Tech Stack:** existing Linux controller Python/Pydantic; target Python/pytest in official SWE-bench images; Docker SDK/CLI from existing harness venv; pinned SWE-bench4.1.0.
**Spec:** D:/Project/CAPSTONES/New_task/VGAR_W9_W16_Deliverables.md M1-W9-5 and docs/repair_runner_interface.md section6. User scope: Docker-only; no native fallback; no design approval round.

## Global Constraints

- Five existing dev IDs/order/base commits and manifest hashes unchanged. No gold/test_patch/F2P/P2P, no inference, no gold rerun or new population.
- Base-only collection uses pytest default discovery/configuration on the unchanged base, identical for graph/BM25. Paired handoff test hints are validated/hash-bound, but not flattened into explicit pytest file arguments: fallback includes deliberately invalid data fixtures. Profile scope marker @pytest-default replays the exact no-selector argv. No patch/overlay applied.
- Immutable official image repo digest + image ID, daemon ID, source HEAD/clean status and tracked Python inventory digests; fixed test/collection argv. Mutable tags cannot qualify profiles.
- Existing three pinned images reused; resolve/freeze two missing image digests BEFORE any collection. No installs in target or Windows/WSL; no image/store reset/prune/settings changes.
- C10GiB/D20GiB free; Windows/Linux4GiB available before pulls/collection. Bounded resource recheck may wait for natural reclaim, never lower gates. Previous W9-4 reclaim grant is not silently expanded.
- Fresh container names, no network/host mounts, private writable container only. Cleanup verifies name/image, no foreign deletion. Global ownership/integrity failure stops run; per-task collection failures/exclusions retain records.
- Task profile minimum fields task_id/base_commit/env_ref/test_command, plus scope/runtime/source/report/timeout/lifecycle provenance. This produces M1 contract/artifact; M2 admission/private lease bridge and oracle policy remain separate.
- Preserve dirty checkout and existing M1/M2/source/config/evidence. No Task Status.md edit, commit/push, W9-4 changes, or next task.

## Review Focus

Wrong manifest/population, mutable/wrong image or daemon, source drift/escaping scope, zero/error/timed-out collection counted as success, and cleanup ambiguity must be tested explicitly. Profile load must revalidate exact argv/hash and never let supplied JSON smuggle shell/volume/extra command arguments.

### Task1: Contract and collection probe

Files: src/vgar/evaluation/harness/task_env.py; src/vgar/evaluation/harness/collection_probe.py; tests/test_task_env.py.
Consumes fixed manifest and paired test_links. Produces strict JSON profile, build_profile/validate_profile and run_probe JSON protocol (target Python>=3.5).
- [x] RED tests: immutable env ref, base/task/scope/hash/argv tampering, profile semantics, real tiny-repo collect without executing failing test, missing/empty/failed collection, base mutation/dirty source.
- [x] Implement strict profile utilities and target-compatible probe; no dependency installation. GREEN targeted tests.

### Task2: Docker orchestration and CLI

Files: task_env.py; scripts/prepare_task_env.py; configs/m1/w9_task_env_profile.json; tests/test_task_env.py.
Consumes Task1 protocol and frozen five-image config. Produces preflight/execute run records and per-task profile/collection evidence.
- [x] RED boundary tests for defaults/no execution, all five records, identity/ownership/timeout/source drift/cleanup veto.
- [x] Implement Docker containers and resource checks, bounded commands, raw logs/profile binding, report protocol and safe finalization. Native/M2 executor are not implemented here.
- [x] GREEN full new tests plus relevant W9-4 and handoff regressions; lint and CLI help.

### Task3: Local qualification, handoff, final review

Files: docs/m1_w9_5_task_env.md; docs/status/m1.md; PROGRESS.md; docs/reviews/2026-10-24-m1-w9-5-docker-review.md; ignored results/m1/w9/m1-w9-5/20261024-docker-only/.
- [x] Read-only runtime inventory; resolve and freeze missing2digests; resource-gated preparation/reuse of five images.
- [x] Preflight actual immutable config, then sequential5base-only collection attempts. Keep each COLLECTED/EXCLUDED with concrete evidence; infrastructure BLOCKED/ERROR is not a scientific exclusion.
- [x] Independently audit profiles/source/commands/node counts/logs/cleanup; final fresh review; fix Important findings in one RED?GREEN pass.
- [x] Update status/report/checkpoint and verify before/after preservation. Stop at W9-5.

No commits in this plan: user's explicit constraint overrides skill commit/worktree defaults. Ledger is ignored results evidence; exact before hashes preserve uncommitted inputs.
