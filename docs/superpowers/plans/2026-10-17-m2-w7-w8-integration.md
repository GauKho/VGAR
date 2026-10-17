# M2 W7-W8 Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the M2 W7-W8 repair pipeline from `M2_week_7_8/src/vgar_m2_w78` into `src/vgar`, make `vgar repair` and the LangGraph `vgar solve` run it with one generation, then delete `M2_week_7_8/`.

**Architecture:** Move code, do not rewrite it. Each M2 module is copied to its role-based location, with relative imports rewritten to absolute `vgar.*` imports and the broken `bootstrap.verify_reference` pin removed. Golden tests written first pin the V11 prompt bytes and `applied.diff` bytes against the saved 2026-10-15 real-model evidence. `vgar solve` becomes `initialize → repair_run → finalize|failed`, where `repair_run` calls `vgar.repair.pipeline.run_repair` exactly once.

**Tech Stack:** Python 3.11, pydantic 2, pytest 8.4, mypy + Ruff (run as subprocesses), git (private worktree), LangGraph, HF transformers in a separate worker process.

**Spec:** `docs/superpowers/specs/2026-10-17-m2-w7-w8-integration-design.md`

## Global Constraints

- `repair_v11.txt` is copied byte-for-byte. Its SHA-256 starts with `ba6d1478`.
- Do not change `build_repair_prompt` logic, `parse_unified_diff`, `PatchPolicy` or `apply_patch` behaviour. Change only imports and path lookup.
- The only registered prompt version is `m2-w78-v11`, and `RepairPolicy.prompt_version` defaults to it. Any other version raises `ValueError('Unregistered or missing prompt version: …')`.
- Keep `run_repair(task, policy, generator, executor, output_root, *, m1_counter, tokenizer, profile=None, temp_root=None, keep_workspace=False, supersedes_run_id=None, rerun_reason=None, feedback=None, deadline=None)`. Drop only `campaign_id`, `attempt_id`, `phase` and `before_generation`.
- `require_trusted_fixture` stays and still gates every native run, for both `vgar repair` and `vgar solve`.
- Do not modify these M1/M2 shared boundary files: `src/vgar/contracts/{repair,evidence,consumer,context}.py` and `src/vgar/graph/token_counter.py`. They are `-text` in `.gitattributes` and use CRLF.
- Use absolute imports (`from vgar.repair.executor import …`), matching the rest of `src/vgar`.
- Byte-attested data must be stored with `-text` in `.gitattributes`.
- No file under `src tests scripts configs examples` may reference `vgar_m2_w78` or `M2_week_7_8` once Task 10 is done.
- Test baseline on 2026-10-17 was 578 passed, 1 skipped, 4 failed. Three failures are in `tests/m2/test_w78_integration.py` and one is `tests/test_hf_model.py::test_local_chat_model_uses_one_greedy_generation_config`. After every task, every previously passing test still passes, except tests that the task deletes and lists in its commit message.
- Run tests with `.venv/Scripts/python.exe -m pytest` from the repository root.

### Module map (used by every task)

| M2 module (`vgar_m2_w78.X`) | New import path |
|---|---|
| `contracts` | `vgar.repair.contracts` (new file; deviation from spec §5.3, see note) |
| `config` (+ `ROOT`) | `vgar.repair.config` (`REPO_ROOT`, `CONFIG_DIR`, `load_config`, `load_task`) |
| `executor` (+ `bootstrap.remaining_timeout`) | `vgar.repair.executor` |
| `diagnostics` | `vgar.repair.diagnostics` |
| `evidence` | `vgar.repair.evidence` |
| `workspace` | `vgar.repair.workspace` (replaces the old module) |
| `test_runner`, `pytest_plugin` | `vgar.repair.test_runner`, `vgar.repair.pytest_plugin` (replace the old module) |
| `checks` | `vgar.repair.static_checks` (replaces the uncommitted 2026-10-16 file) |
| `context_adapter`, `context_presentation` | `vgar.repair.context_adapter`, `vgar.repair.context_presentation` |
| `prompt` + `prompts/repair_v11.txt` | `vgar.repair.prompt` + `src/vgar/repair/prompts/repair_v11.txt` |
| `patch`, `verification`, `test_selection`, `pipeline` | `vgar.repair.patch`, `vgar.repair.verification`, `vgar.repair.test_selection`, `vgar.repair.pipeline` |
| `generator` | `vgar.models.generator` |
| `generator_hf`, `hf_backend`, `hf_diagnostics`, `hf_worker`, `model_worker`, `local_chat` | `vgar.models.huggingface.<same name>` |

**Deviation from spec §5.3:** the M2 types `safe_path`, `safe_selector`, `RepairTask`, `RepairPolicy` and `ModelProfile` go into a new file `src/vgar/repair/contracts.py`, not into `contracts/repair.py`. `contracts/repair.py` is a frozen M1/M2 boundary file (CRLF bytes, `-text`), and the M2 docstring already says these are internal configuration types, not public DTOs.

**Porting a M2 test:** copy the file to `tests/m2/w78/test_w78_<original stem>.py`. The prefix avoids basename clashes with `tests/m2/test_workspace.py` and `tests/test_test_selection.py`. Then:
- replace `api('X')` with the module from the table, imported at the top;
- replace `from conftest import …` with `from w78_support import …`;
- replace `from test_bootstrap import api` with nothing;
- delete any test function that exercises bootstrap, campaign, V1–V10 prompts or relocation, and list each deleted test name in the commit message.

### Rewrites applied when moving any M2 source file

- `from .bootstrap import verify_reference`: delete the import and every `verify_reference(...)` call, including `run.record['reference'] = verify_reference(deadline=deadline)`.
- `from .bootstrap import remaining_timeout` → `from vgar.repair.executor import remaining_timeout`.
- `from .bootstrap import ROOT` → `from vgar.repair.config import REPO_ROOT`.
- `from .X import …` → the absolute path from the table.
- String `'vgar_m2_w78.pytest_plugin'` → `'vgar.repair.pytest_plugin'`.
- String `'vgar_m2_w78.hf_worker'` → `'vgar.models.huggingface.hf_worker'`.

## Review Focus

1. **`vgar run`/`vgar chat` on a repo that M2's stricter workspace rejects.** M2's workspace rejects `.gitattributes`, links, files over 16 MB and totals over 256 MB, and it does not skip `artifacts/`, `logs/` or `node_modules/`. The user should get a clear `ValueError` message, not a traceback from deep inside git. Test: Task 4 `test_w78_cli_run_rejects_gitattributes_with_clear_error`.
2. **A task file whose relative `source_repo`/`bundle_directory` is resolved against the CWD instead of the task file's folder.** Running from another directory must still work. Test: Task 3 `test_load_task_resolves_paths_relative_to_task_file`.
3. **A config whose `snapshot` uses `~`.** It must expand to the user's home, because the Qwen snapshot lives on `C:` while the repo is on `D:`. Test: Task 3 `test_load_config_expands_user_home_in_model_paths`.
4. **`vgar solve` given a task outside `trusted_fixtures.json`.** It must end `FAILED` with the pipeline's reason and leave the source untouched, not raise. Test: Task 8 `test_solve_untrusted_task_fails_without_touching_source`.
5. **The pytest plugin import in the child pytest process.** M2 relied on its package being pip-installed. The new name must import from the root `.venv` with no `PYTHONPATH`. Test: Task 4 `test_w78_run_tests_child_process_loads_plugin_without_pythonpath`.

---

### Task 1: Golden fixtures, configs and red golden test

**Files:**
- Create (copy): `examples/m2/{tasks,handoffs,snapshots}/**` from `M2_week_7_8/examples/{tasks,handoffs,snapshots}`
- Create (copy): `tests/fixtures/m2/reference_patches/*.diff` from `M2_week_7_8/tests/fixtures/reference_patches/`
- Create (copy): `tests/fixtures/m2/golden_v11/{A,B,C}/{prompt.txt,raw_model_output.txt,applied.diff,evidence_bundle.json,run_record.json}` from `M2_week_7_8/results/final_acceptance/2026-10-15-v11-r002/{A,B,C}/<the single run dir>/`
- Create (copy): `configs/m2/trusted_fixtures.json`, `configs/m2/static/mypy.ini`, `configs/m2/static/ruff.toml`
- Create: `configs/m2/demo.json`
- Modify: `.gitattributes`
- Create: `tests/m2/w78/w78_support.py`, `tests/m2/w78/conftest.py`, `tests/m2/w78/test_w78_golden_v11.py`

**Interfaces:**
- Produces: the fixture paths above; `w78_support.REPO`, `w78_support.CharacterChatTokenizer` (copied from M2 `tests/conftest.py`); fixture `m1_case(tmp_path) -> (RepairTask, LocalTokenizerCounter)`. The fixture copies `examples/m2/snapshots/single_file_login` and `examples/m2/handoffs/single_file_login` into `tmp_path`. It replaces M2's `artifacts/m1/w7-w8/handoff-demos/20261014T072245Z-…` bundle, which does not exist on this machine.

- [ ] **Step 1: Copy the data files with `cp -r`, without opening or re-saving them.** Then add these lines to `.gitattributes` under the M2 block:
  ```
  examples/m2/** -text
  configs/m2/** -text
  tests/fixtures/m2/** -text
  src/vgar/repair/prompts/** -text
  ```
- [ ] **Step 2: Verify the copies are byte-identical.** Run `diff -r M2_week_7_8/examples/tasks examples/m2/tasks`, do the same for `handoffs`, `snapshots` and `reference_patches`, and run `sha256sum` on the three golden `prompt.txt`. Expected: no diff output, and hashes start with `b39baa82` (A), `4f234c25` (B) and `c37a5ef2` (C).
- [ ] **Step 3: Write `configs/m2/demo.json`.** Start from `M2_week_7_8/config/demo.json` and change only these fields:
  - `"prompt_version": "m2-w78-v11"`
  - `"snapshot": "~/.cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554"`
  - `"interpreter": "../../.venv/Scripts/python.exe"`
  - `"tokenizer_manifest": "../../artifacts/m2/w5-w6/tokenizer_manifest.json"`
- [ ] **Step 4: Write the failing golden test** in `tests/m2/w78/test_w78_golden_v11.py`:

```python
CASES = [
    ("A", "single_file_login", "b39baa82f293cf18185df8b3fa227f7d9fdddf5f1e3bda0064fb05e712dada02", 1299),
    ("B", "multi_file_invoice", "4f234c251402dbbfb6f6cdc3d4838d29fc81757c38260aa53b1d0b06de90f326", 1769),
    ("C", "missing_links", "c37a5ef27071c9635baba914fdf95408610a729f138fbe59a3df8e85bf07a3d3", 1169),
]

@pytest.mark.parametrize("letter,case,prompt_sha,tokens", CASES)
def test_v11_fake_run_reproduces_saved_real_evidence(letter, case, prompt_sha, tokens, tmp_path):
    from vgar.graph.token_counter import LocalTokenizerCounter
    from vgar.models.generator import FakeGenerator
    from vgar.models.huggingface.local_chat import LocalChatTokenizer
    from vgar.repair.config import CONFIG_DIR, load_config, load_task
    from vgar.repair.pipeline import run_repair
    golden = REPO / "tests/fixtures/m2/golden_v11" / letter
    policy, profile = load_config(CONFIG_DIR / "demo.json")
    task = load_task(REPO / "examples/m2/tasks" / f"{case}.json")
    run = run_repair(task, policy, FakeGenerator((golden / "raw_model_output.txt").read_text(encoding="utf-8")),
                     None, tmp_path / "runs", m1_counter=LocalTokenizerCounter(profile.tokenizer_manifest),
                     tokenizer=LocalChatTokenizer(profile.tokenizer_manifest), temp_root=tmp_path / "ws")
    assert run.record["status"] == "PASS"
    assert run.record["stages"]["prompt"]["input_tokens"] == tokens
    assert (run.directory / "prompt.txt").read_bytes() == (golden / "prompt.txt").read_bytes()
    assert hashlib.sha256((run.directory / "prompt.txt").read_bytes()).hexdigest() == prompt_sha
    assert (run.directory / "applied.diff").read_bytes() == (golden / "applied.diff").read_bytes()
```

  The spike on 2026-10-17 ran the *old* package this way. It gave PASS and byte-equal `prompt.txt`/`applied.diff` for A, B and C, with the same token counts under tokenizers 0.22.2. That makes spec §6 test 3 (old package vs new code) redundant, so this plan does not add it.
- [ ] **Step 5: Run the test and confirm it fails.** Run `.venv/Scripts/python.exe -m pytest tests/m2/w78/test_w78_golden_v11.py -q`. Expected: 3 failed with `ModuleNotFoundError: No module named 'vgar.repair.config'`.
- [ ] **Step 6: Commit.** Mark the golden test `xfail(strict=True, reason="pipeline not migrated yet")` so the suite stays green, then commit with `test(m2): add W7-W8 golden V11 fixtures and red golden test`.

### Task 2: Remove the exact-edit `solve` workflow

**Files:**
- Delete: `src/vgar/agents/nodes/prepare.py`, `src/vgar/agents/nodes/repair.py`, `src/vgar/agents/nodes/verify.py`, `tests/unit/test_workflow.py`, `src/vgar/repair/static_checks.py` (uncommitted), `tests/unit/test_static_checks.py` (uncommitted)
- Modify: `src/vgar/agents/nodes/__init__.py`, `src/vgar/agents/workflow.py`, `src/vgar/agents/routes.py`, `src/vgar/agents/runtime.py`, `src/vgar/cli.py` (`cmd_solve` and the `solve` subparser)

**Interfaces:**
- Produces: `vgar.agents.workflow` keeps `run_task` and `build_workflow` as names, but in this interim state `cmd_solve` prints `solve is being migrated to the M2 pipeline` and returns 2. Task 8 restores it. `agents/core.py`, `vgar run` and `vgar chat` are untouched.

- [ ] **Step 1: Back up the uncommitted 2026-10-16 work.** Run `git diff -- src/vgar/agents/nodes tests/unit/test_workflow.py > m2-temp/2026-10-16-static-checks.patch`, then `cp src/vgar/repair/static_checks.py tests/unit/test_static_checks.py m2-temp/`. `m2-temp/` is gitignored. Expected: the patch file is non-empty.
- [ ] **Step 2: Delete and strip.** Delete the files listed above. Remove their imports and graph nodes, and leave `workflow.py` with `initialize → finalize`. Remove `route_after_repair`/`route_after_verify` if nothing else imports them (check with grep). Remove the `Runtime.agent`/`make_agent`/`sandboxed` fields if only the deleted nodes used them.
- [ ] **Step 3: Run the suite.** Run `.venv/Scripts/python.exe -m pytest -q`. Expected: the baseline minus the deleted `test_workflow.py` tests. `tests/unit/test_state.py` and `tests/unit/test_tool_budget.py` still pass.
- [ ] **Step 4: Commit** with `refactor(agents): remove exact-edit solve workflow ahead of M2 pipeline`, listing the deleted tests and noting that the 2026-10-16 static-check work is backed up in `m2-temp/`.

### Task 3: Foundation — contracts, config, executor, diagnostics, evidence

**Files:**
- Create: `src/vgar/repair/contracts.py`, `src/vgar/repair/config.py`, `src/vgar/repair/executor.py`, `src/vgar/repair/diagnostics.py`, `src/vgar/repair/evidence.py`
- Test: `tests/m2/w78/test_w78_contracts.py`, `test_w78_executor.py`, `test_w78_evidence.py`, `test_w78_config.py`

**Interfaces:**
- Produces:
  - `vgar.repair.contracts`: `safe_path(str) -> str`, `safe_selector(str) -> str`, `RepairTask`, `RepairPolicy` (default `prompt_version='m2-w78-v11'`), `ModelProfile`.
  - `vgar.repair.config`: `REPO_ROOT: Path` (= `Path(__file__).resolve().parents[3]`), `CONFIG_DIR = REPO_ROOT / 'configs/m2'`, `load_config(path) -> tuple[RepairPolicy, ModelProfile]`, `load_task(path) -> RepairTask`.
  - `vgar.repair.executor`: `utc_now`, `clean_environment`, `run_bounded`, `NativeExecutor`, and `remaining_timeout(deadline=None, cap=30)` (moved from `bootstrap.py` unchanged).
  - `vgar.repair.diagnostics`: `exception_details`, `patch_diagnostics`.
  - `vgar.repair.evidence`: `digest`, `encode_json`, `atomic_json`, `RunHandle`, `begin_run`.

- [ ] **Step 1: Write the failing tests.**
  - Port M2 `test_contracts.py`, `test_executor.py` and `test_evidence.py`. In `test_evidence.py`, drop `test_test_recorder_keeps_exact_exit_and_logs`, because it drives `scripts/record_tests.py`, which is not migrated.
  - Add to `test_w78_config.py`:

```python
def test_load_task_resolves_paths_relative_to_task_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task = load_task(REPO / "examples/m2/tasks/single_file_login.json")
    assert task.source_repo == (REPO / "examples/m2/snapshots/single_file_login").resolve()
    assert task.bundle_directory == (REPO / "examples/m2/handoffs/single_file_login").resolve()

def test_load_config_expands_user_home_in_model_paths():
    policy, profile = load_config(CONFIG_DIR / "demo.json")
    assert policy.prompt_version == "m2-w78-v11"
    assert profile.snapshot.is_relative_to(Path.home())
    assert profile.interpreter == (REPO / ".venv/Scripts/python.exe").resolve()

def test_repair_policy_defaults_to_v11():
    assert RepairPolicy().prompt_version == "m2-w78-v11"
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/Scripts/python.exe -m pytest tests/m2/w78 -q -k "contracts or executor or evidence or config"`. Expected: ImportError failures.
- [ ] **Step 3: Implement by moving the M2 files.**
  - Move them using the rewrite rules.
  - Change the `RepairPolicy.prompt_version` default to `'m2-w78-v11'`.
  - `load_config` is M2's version, except that it applies `Path(model[field]).expanduser()` before joining with `path.parent`.
  - `load_task(path)` is the task-loading block from M2 `cli.py`: it resolves `source_repo` and `bundle_directory` against `path.parent`, then calls `RepairTask.model_validate`.
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: all pass. Then run the full suite. Expected: baseline.
- [ ] **Step 5: Commit** with `feat(repair): move M2 contracts, config, executor, diagnostics, evidence`.

### Task 4: Replace workspace and test runner, add static checks, migrate callers

**Files:**
- Replace: `src/vgar/repair/workspace.py`, `src/vgar/repair/test_runner.py`
- Create: `src/vgar/repair/pytest_plugin.py`, `src/vgar/repair/static_checks.py`
- Delete: `src/vgar/repair/baseline.py`, `src/vgar/repair/evidence_writer.py`, `tests/m2/test_workspace.py`, `tests/m2/test_test_runner.py`, `tests/m2/test_baseline.py`, `tests/m2/test_evidence_writer.py`, `scripts/record_m2_test.py`, `scripts/run_m2_baseline.py`, `scripts/smoke_w3_w4_full.py`, `scripts/smoke_w3_w4_repair_loop.py`
- Modify: `src/vgar/cli.py` (`sandbox`, `cmd_run`), `src/vgar/mcp/servers/repository_server.py` (import only), `scripts/smoke_w3_w4_agent.py`
- Test: `tests/m2/w78/test_w78_workspace.py`, `test_w78_test_runner.py`, `test_w78_static_checks.py`, `test_w78_cli_run.py`

**Interfaces:**
- Consumes: Task 3 modules.
- Produces:
  - `vgar.repair.workspace`: M2's `IGNORED`, `inventory(root) -> dict[str, str]`, `WorkspaceLease` (`path`, `private`, `before`, `worktree_id`, `active`, `keep`, `assert_original()`), `create_workspace(source, temp_root, policy=None, *, deadline=None)`.
  - The same module also keeps the two old helpers unchanged, because MCP and `vgar run` use them: `safe_relative_path(value) -> Path` and `fingerprint_source(source_repo) -> str`, together with the private `_source_files` they need.
  - `vgar.repair.test_runner`: `collect_tests(lease, selectors, executor, timeout_seconds=120) -> dict`, `run_tests(lease, selectors, executor, timeout_seconds) -> dict`.
  - `vgar.repair.static_checks`: `run_static_checks(lease, targets, policy, executor) -> dict`, with keys `syntax`, `mypy`, `ruff`, `config_hashes`. Config paths: `CONFIG_DIR / 'static/mypy.ini'` and `CONFIG_DIR / 'static/ruff.toml'`.

- [ ] **Step 1: Write the failing tests.**
  - Port M2 `test_workspace.py` and `test_test_runner.py`.
  - Port from the backed-up `m2-temp/test_static_checks.py` the cases that still make sense against the new API: a type error fails mypy, an undefined name fails Ruff, repository config cannot weaken the checks, and no cache is left in the workspace. Drop the `changed_python_files` tests.
  - Add:

```python
def test_w78_run_tests_child_process_loads_plugin_without_pythonpath(m1_case, tmp_path, monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)
    task, _ = m1_case
    with create_workspace(task.source_repo, tmp_path / "ws") as lease:
        result = collect_tests(lease, ("tests",), NativeExecutor(lease), 60)
    assert result["status"] == "PASS"
    assert "tests/test_auth.py::test_login_rejects_whitespace" in result["node_ids"]

def test_w78_cli_run_rejects_gitattributes_with_clear_error(tmp_path, capsys):
    (tmp_path / "repo").mkdir(); (tmp_path / "repo/.gitattributes").write_text("* text\n")
    with pytest.raises(ValueError, match="Attribute transformations are unsupported"):
        with sandbox_workspace(tmp_path / "repo", tmp_path / "ws"):
            pass
```

  `sandbox_workspace` is the workspace-only half of `cli.sandbox`. Extract it as `sandbox_workspace(repo: Path, root: Path)`, a context manager yielding the lease, so it can be tested without indexing.
- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/Scripts/python.exe -m pytest tests/m2/w78 -q -k "workspace or test_runner or static or cli_run"`. Expected: failures on the missing API and plugin.
- [ ] **Step 3: Implement the modules and migrate callers.**
  - Move the M2 files.
  - Append the two old helpers to `workspace.py`.
  - In `cli.py`:
    - `sandbox` logs `fingerprint_source(lease.path)` in place of `lease.source_hash_before`.
    - `cmd_run` stores `fingerprint_source(lease.path)` right after the workspace is created, and compares against it at `workspace_change_check`.
    - Independent verification becomes `verdict = run_tests(lease, (args.selector,), NativeExecutor(lease), 120)` with `ok = verdict["status"] == "PASS"`. Log `status`, `outcomes` and `command.exit_code`.
  - In `smoke_w3_w4_agent.py`, make the same three substitutions.
  - Delete the listed files.
- [ ] **Step 4: Run all tests.** Run the Step 2 command, then the full suite. Expected: all pass, with the baseline minus the deleted tests. `tests/test_mcp_tool_contract.py` and `tests/test_agent_tools.py` must still pass, which proves `safe_relative_path` semantics are unchanged.
- [ ] **Step 5: Commit** with `feat(repair): replace workspace/test runner with M2 versions; add static checks`, listing the deleted tests and scripts.

### Task 5: Repair layer — context, prompt, patch, verification, test selection

**Files:**
- Create: `src/vgar/repair/context_adapter.py`, `context_presentation.py`, `prompt.py`, `prompts/repair_v11.txt` (copied with `cp`), `patch.py`, `verification.py`, `test_selection.py`
- Test: `tests/m2/w78/test_w78_context_adapter.py`, `test_w78_prompt.py`, `test_w78_prompt_v11.py`, `test_w78_patch.py`, `test_w78_verification.py`, `test_w78_test_selection.py`

**Interfaces:**
- Consumes: Tasks 3–4.
- Produces:
  - `load_handoff(task, m1_counter, counter_label) -> ValidatedHandoff`; `present_context(handoff, *, absolute_lines=False, patch_contract=False) -> tuple[str, dict]`.
  - `template_path(version) -> Path`, which resolves to `Path(__file__).parent / 'prompts' / f'repair_v{n}.txt'`; `build_repair_prompt(task, handoff, baseline, tokenizer, policy, *, feedback=None) -> PromptArtifact`.
  - `PatchPolicy`, `ParsedPatch`, `parse_unified_diff(raw, policy)`, `apply_patch(lease, patch, executor)`.
  - `expand_required`, `capture_baseline(task, lease, executor, policy)`, `assess_transition(baseline, post)`, `verify_patch(task, lease, apply_result, baseline, selection, executor, policy)`.
  - `select_relevant_tests(changed_files, handoff, task) -> dict`.

- [ ] **Step 1: Write the failing tests.**
  - Port M2 `test_context_adapter.py`, `test_prompt.py`, `test_prompt_v11.py`, `test_patch.py`, `test_verification.py` and `test_test_selection.py`.
  - In `test_w78_prompt_v11.py`, read the template from `REPO / 'src/vgar/repair/prompts/repair_v11.txt'`.
  - Add:

```python
def test_only_v11_is_registered():
    assert hashlib.sha256(template_path("m2-w78-v11").read_bytes()).hexdigest().startswith("ba6d1478")
    for version in ("m2-w78-v1", "m2-w78-v10", "m2-w78-v12"):
        with pytest.raises(ValueError, match="Unregistered or missing prompt version"):
            template_path(version)
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/Scripts/python.exe -m pytest tests/m2/w78 -q -k "context or prompt or patch or verification or selection"`. Expected: ImportError failures.
- [ ] **Step 3: Implement by moving the M2 files.**
  - Apply the rewrite rules.
  - In `prompt.py`, `template_path` changes only the folder. Keep the regex check, and the existing `is_file()` check raises for unregistered versions.
  - Leave the V3/V4/adaptive branches in `build_repair_prompt` as they are: V11 takes the `adaptive`/`replacement` path, and removing the branches is outside this plan.
- [ ] **Step 4: Run all tests.** Run the same command, then the full suite. Expected: all pass.
- [ ] **Step 5: Commit** with `feat(repair): move M2 context, V11 prompt, patch, verification, test selection`.

### Task 6: Generators — fake and Hugging Face worker

**Files:**
- Create: `src/vgar/models/generator.py`, `src/vgar/models/huggingface/{generator_hf,hf_backend,hf_diagnostics,hf_worker,model_worker,local_chat}.py`
- Modify: `pyproject.toml` (`dev` extras add `"mypy==2.4.0"` and `"ruff==0.17.0"`, the versions installed in `.venv`)
- Test: `tests/m2/w78/test_w78_generator.py`, `test_w78_hf_adapter.py`, `test_w78_local_chat.py`, `test_w78_generation_diagnostics.py`, `test_w78_tokenizer_flags.py`

**Interfaces:**
- Consumes: Tasks 3 and 5.
- Produces:
  - `FakeGenerator(raw_text)` with `.mode == 'fake'` and `.generate(prompt, profile, timeout_seconds) -> dict`.
  - `HFGenerator(profile, worker_root, policy=None)` and `HFChatTokenizer(generator, policy, timeout=120)`.
  - `LocalChatTokenizer(manifest_path)` with `.apply_chat_template(messages, *, tokenize, add_generation_prompt)`.
  - The worker is started as `(profile.interpreter, '-B', '-m', 'vgar.models.huggingface.hf_worker', request, response)`, with `PYTHONPATH=str(REPO_ROOT / 'src')`.

- [ ] **Step 1: Write the failing tests.** Port the five M2 test files. In `test_w78_local_chat.py`, the manifest path is `REPO / 'artifacts/m2/w5-w6/tokenizer_manifest.json'`. Add a test that `HFGenerator`'s worker command contains `'vgar.models.huggingface.hf_worker'`, using the existing fake-interpreter pattern in `test_hf_adapter.py`.
- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/Scripts/python.exe -m pytest tests/m2/w78 -q -k "generator or hf or local_chat or tokenizer"`. Expected: ImportError failures.
- [ ] **Step 3: Implement by moving the M2 files** and applying the rewrite rules. `vgar.models.huggingface/__init__.py` stays unchanged, so it does not import torch eagerly.
- [ ] **Step 4: Run all tests.** Run the same command, then the full suite. Expected: all pass. `tests/test_hf_model.py` keeps its single pre-existing failure.
- [ ] **Step 5: Commit** with `feat(models): move M2 fake and HF worker generators`.

### Task 7: Pipeline and `vgar repair`; golden test turns green

**Files:**
- Create: `src/vgar/repair/pipeline.py`
- Modify: `src/vgar/cli.py` (add `cmd_repair` and the `repair` subparser), `tests/m2/w78/test_w78_golden_v11.py` (remove the xfail)
- Test: `tests/m2/w78/test_w78_pipeline.py`, `test_w78_finalization.py`, `test_w78_workspace_cleanup.py`, `test_w78_review_guards.py`, `test_w78_diagnostic_logging.py`, `test_w78_cli_repair.py`

**Interfaces:**
- Consumes: Tasks 3–6.
- Produces:
  - `run_repair(...)` with the signature in Global Constraints, returning a `RunHandle` with `.path`, `.directory` and `.record`.
  - `require_trusted_fixture(task)`, which reads `CONFIG_DIR / 'trusted_fixtures.json'`.
  - The default `temp_root` is `REPO_ROOT / '.workspaces'`. Add `.workspaces/` to `.gitignore`.
  - `source_fingerprint` hashes `.py/.txt/.json/.ini/.toml` files under `src/vgar/repair`, `src/vgar/models`, `src/vgar/contracts` and `configs/m2`, with keys relative to `REPO_ROOT`.
  - `vgar repair --task PATH [--config PATH] --mode fake|real [--output-root PATH] [--keep-workspace] [--supersedes-run-id ID --rerun-reason TEXT]`. It prints the run record path and exits 0 for PASS, 1 for FAIL, 2 for ERROR. Defaults: `--config CONFIG_DIR/demo.json`, `--output-root REPO_ROOT/results/repair`. Fake mode uses `tests/fixtures/m2/reference_patches/<task_id>.diff` and `LocalChatTokenizer`. Real mode uses `HFGenerator(profile, output_root / 'model-workers', policy)` and `HFChatTokenizer`. Any exception writes a `repair-config-error` run and exits 2, as in M2 `cli.py`.
  - `build_generation(mode, task, policy, profile, output_root) -> tuple[generator, tokenizer, LocalTokenizerCounter]` lives in `vgar.repair.pipeline` and holds that fake/real selection. `cmd_repair` calls it, and so does Task 8.

- [ ] **Step 1: Write the failing tests.**
  - Port M2 `test_pipeline.py`, `test_finalization.py`, `test_workspace_cleanup.py`, `test_review_guards.py` (drop the `bootstrap` test) and `test_diagnostic_logging.py`. Its `scripts/run_demo.py` subprocess calls become `[sys.executable, '-m', 'vgar.cli', 'repair', …]`.
  - Remove the xfail marker from the golden test.
  - Add to `test_w78_cli_repair.py`:

```python
@pytest.mark.parametrize("case", ["single_file_login", "multi_file_invoice", "missing_links"])
def test_vgar_repair_fake_passes_each_fixture(case, tmp_path):
    code = cli.main(["repair", "--task", str(REPO / f"examples/m2/tasks/{case}.json"),
                     "--mode", "fake", "--output-root", str(tmp_path / "runs")])
    assert code == 0

def test_vgar_repair_missing_task_writes_error_run(tmp_path, capsys):
    code = cli.main(["repair", "--task", str(tmp_path / "missing.json"), "--mode", "fake",
                     "--output-root", str(tmp_path / "runs")])
    assert code == 2
    assert Path(capsys.readouterr().out.strip().splitlines()[-1]).is_file()
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/Scripts/python.exe -m pytest tests/m2/w78 -q`. Expected: failures on `vgar.repair.pipeline` and `repair` subcommand.
- [ ] **Step 3: Implement.**
  - Move `pipeline.py`, apply the rewrite rules, and remove the campaign-only parameters along with the code that uses them.
  - `cmd_repair` is synchronous logic in an `async def`, to match the existing `fn` dispatch through `asyncio.run`.
- [ ] **Step 4: Run all tests.** Run the Step 2 command, then the full suite. Expected: all pass, including all 3 golden cases.
- [ ] **Step 5: Commit** with `feat(repair): move M2 pipeline and add vgar repair CLI`.

### Task 8: `vgar solve` runs the M2 pipeline once

**Files:**
- Create: `src/vgar/agents/nodes/repair_run.py`
- Modify: `src/vgar/agents/workflow.py`, `src/vgar/agents/routes.py`, `src/vgar/agents/runtime.py`, `src/vgar/agents/state.py`, `src/vgar/agents/nodes/__init__.py`, `src/vgar/agents/nodes/finalize.py`, `src/vgar/agents/nodes/initialize.py`, `src/vgar/cli.py` (`cmd_solve`, `solve` subparser)
- Test: `tests/unit/test_workflow.py` (new content)

**Interfaces:**
- Consumes: `run_repair`, `build_generation`, `load_task`, `load_config` and `FakeGenerator` from earlier tasks.
- Produces:
  - `Runtime` gains `mode: Literal['fake','real'] = 'fake'`, `config_path: Path = CONFIG_DIR / 'demo.json'`, `output_root: Path = REPO_ROOT / 'results/solve'`, `generator: Any = None` (an injectable test override), and keeps `keep_workspace`.
  - `run_task(*, task_path: Path, runtime: Runtime | None = None) -> VGARState`.
  - The initial state contains `task_id` (from the task file), `task_path`, `repo_path` (= `task.source_repo`), `issue_text`, `failing_tests` and `max_iterations=1`.
  - The node `repair_run(state, runtime) -> dict` sets `attempts=1`, `run_record_path`, `evidence` (the parsed `evidence_bundle.json`, or `{}`), `repair_status` (`PASS|FAIL|ERROR`), and `failure_reason` (`None` on PASS, otherwise the run record `reason`).
  - `route_after_repair_run`: `'finalize'` if `repair_status == 'PASS'`, else `'failed'`.
  - `finalize` keeps its source-hash check.
  - `cmd_solve`: `vgar solve --task PATH [--mode fake|real] [--keep]`. It prints status and the run record path, and exits 0 when `COMPLETED`.

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_workflow.py`:

```python
def test_solve_fake_completes_with_m2_evidence(tmp_path):
    state = asyncio.run(run_task(task_path=REPO / "examples/m2/tasks/single_file_login.json",
                                 runtime=Runtime(output_root=tmp_path / "runs")))
    assert state["status"] == "COMPLETED" and state["attempts"] == 1
    assert state["evidence"]["verification"]["patch_applied"] is True
    assert Path(state["run_record_path"]).is_file()

def test_solve_invalid_diff_fails_once_without_retry(tmp_path):
    state = asyncio.run(run_task(task_path=REPO / "examples/m2/tasks/single_file_login.json",
                                 runtime=Runtime(output_root=tmp_path / "runs", generator=FakeGenerator("not a diff"))))
    assert state["status"] == "FAILED" and state["attempts"] == 1
    assert state["failure_reason"] == "PATCH_PARSE_ERROR"

def test_solve_untrusted_task_fails_without_touching_source(tmp_path):
    task = json.loads((REPO / "examples/m2/tasks/single_file_login.json").read_text(encoding="utf-8"))
    shutil.copytree(REPO / "examples/m2/snapshots/single_file_login", tmp_path / "src")
    (tmp_path / "src/auth.py").write_bytes(b"def login(value):\n    return False\n")
    before = (tmp_path / "src/auth.py").read_bytes()
    task.update(source_repo=str(tmp_path / "src"),
                bundle_directory=str(REPO / "examples/m2/handoffs/single_file_login"))
    (tmp_path / "task.json").write_text(json.dumps(task), encoding="utf-8")
    state = asyncio.run(run_task(task_path=tmp_path / "task.json", runtime=Runtime(output_root=tmp_path / "runs")))
    assert state["status"] == "FAILED" and state["failure_reason"]
    assert (tmp_path / "src/auth.py").read_bytes() == before
```

  `tests/unit/test_state.py` still passes, because `initialize_task` keeps its validation.
- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/Scripts/python.exe -m pytest tests/unit -q`. Expected: TypeError or ImportError on `run_task(task_path=…)`.
- [ ] **Step 3: Implement.**
  - `repair_run` calls `build_generation(runtime.mode, …)` from Task 7. If `runtime.generator` is set, it replaces the returned generator.
  - Wrap the node with `@instrument_node("repair_run")`.
  - The workflow is `START → initialize → repair_run → (finalize|failed) → END`, with `recursion_limit=8`.
- [ ] **Step 4: Run all tests.** Run the same command, then the full suite. Expected: all pass.
- [ ] **Step 5: Commit** with `feat(agents): run vgar solve through the M2 pipeline with one generation`.

### Task 9: Phase 1 acceptance

**Files:**
- Modify: `README.md` (one short section: `vgar repair` / `vgar solve` usage, fake vs real)

- [ ] **Step 1: Run the full suite.** Run `.venv/Scripts/python.exe -m pytest -q`. Expected: no new failures against the baseline, and the deleted tests are accounted for in the commit messages.
- [ ] **Step 2: Run `vgar repair` in fake mode on each fixture.** Run `.venv/Scripts/python.exe -m vgar.cli repair --task examples/m2/tasks/<case>.json --mode fake` for each of the 3 cases. Expected: exit 0 each time.
- [ ] **Step 3: Run `vgar solve` in fake mode on each fixture.** Run `.venv/Scripts/python.exe -m vgar.cli solve --task examples/m2/tasks/<case>.json` for each of the 3 cases. Expected: `[status] COMPLETED` each time.
- [ ] **Step 4: Write the README section and commit** with `docs: document vgar repair and vgar solve (M2 W7-W8)`.

### Task 10: Phase 2 — remove `M2_week_7_8/`, then run the real model

**Files:**
- Delete: `M2_week_7_8/`, `tests/m2/test_w78_integration.py`, `tests/m2/test_w78_preservation.py`, `scripts/check_m2_integration.py`, `run_m2_abc.ps1`
- Modify: `.gitattributes` (remove the `M2_week_7_8/** -text` line)

- [ ] **Step 1: Rename the folder.** Run `mv M2_week_7_8 M2_week_7_8.off`.
- [ ] **Step 2: Rerun the checks without the folder.** Rerun the Task 9 steps 1–3, then `grep -rn "vgar_m2_w78\|M2_week_7_8" src tests scripts configs examples`. Expected:
  - the suite passes except the 3 `test_w78_integration.py` tests and `test_w78_preservation.py`, which are about the folder;
  - fake A/B/C exit 0;
  - grep finds only the four files listed for deletion.
- [ ] **Step 3: Get the user's approval.** Show the user the Step 2 output and ask for explicit confirmation to delete the 307 tracked files under `M2_week_7_8/`. Do not continue without a yes.
- [ ] **Step 4: Delete and commit.** On yes, run `mv M2_week_7_8.off M2_week_7_8 && git rm -r -q M2_week_7_8` and remove the other listed files and the `.gitattributes` line. Run the full suite. Expected: baseline minus the deleted tests, with no failures except the pre-existing `test_hf_model` one. Commit with `chore(m2): remove M2_week_7_8 after integration into src/vgar`.
- [ ] **Step 5: Run the real model.** For each of the 3 cases, run `.venv/Scripts/python.exe -m vgar.cli repair --task examples/m2/tasks/<case>.json --mode real --output-root results/m2-real/2026-10-17`. This uses the RTX 4050 (6 GB) with `device_map=auto`, so expect CPU offload and slow generation, within `generation_timeout=900`. Expected: exit 0 for each case. Record status, input/output tokens and duration per case.
- [ ] **Step 6: Report.** If any real run is not PASS, read `run_record.json` (`stages`, `error_detail`), investigate once, and report the cause to the user. Do not change the prompt, parser or policy to make it pass. Report the results table to the user. `results/` is gitignored, so nothing from the real run is committed.
