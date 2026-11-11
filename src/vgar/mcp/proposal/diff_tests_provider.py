"""TV3 EV-3. Run a host-admitted diff against baseline and candidate tests."""
from __future__ import annotations

import re
import shutil
import threading
import time
from uuid import uuid4

import anyio

from vgar.graph.storage_capabilities import canonical_bytes
from vgar.repair.admission import prepare_admitted_workspace, validate_admission
from vgar.repair.contracts import RepairPolicy, RepairTask
from vgar.repair.docker_executor import DockerExecutor
from vgar.repair.evidence import atomic_json, digest, encode_json
from vgar.repair.patch import PatchPolicy, apply_patch, parse_unified_diff
from vgar.repair.pipeline import DeadlineExecutor, require_trusted_fixture
from vgar.repair.semantic_contract import ContractExecutor, SemanticContract
from vgar.repair.test_runner import run_tests
from vgar.repair.verification import assess_transition, expand_required
from vgar.repair.verification_checks import inventory_hash
from vgar.repair.workspace import create_workspace, inventory, safe_relative_path

from . import contracts as c
from .context import cancel_request, check_context, check_source, request_commit_guard
from .locking import no_links
from .security import resolve_read_path

PROFILE = "tv3-ev3-v1"


class DiffTestsProvider:
    """Register via CoreTools with lifecycle guarded-v1 and candidate_workspace."""

    def __init__(self, task: RepairTask, policy: RepairPolicy, binding: c.SnapshotBinding, *,
                 candidate_workspace: str, admission=None, approved_fixture_diffs: tuple[str, ...] = (),
                 snapshot_id: str | None = None, semantic_contract: SemanticContract | None = None):
        self._task = RepairTask.model_validate(task.model_dump())
        self._policy = RepairPolicy.model_validate(policy.model_dump())
        self._binding = c.SnapshotBinding.model_validate(binding.model_dump())
        if (self._task.task_id, self._task.graph_version) != (binding.task_id, binding.snapshot_hash):
            raise ValueError("Diff tests require a task bound to the selected graph")
        if not self._task.failing_selectors or not self._task.fallback_scope or not self._task.allowed_source_paths:
            raise ValueError("Diff tests require failing selectors, regression scope and editable paths")
        if len(safe_relative_path(candidate_workspace).parts) != 1:
            raise ValueError("Diff tests require one host-owned workspace name")
        self.candidate_workspace = candidate_workspace
        if snapshot_id is not None and re.fullmatch(r"sha256:[0-9a-f]{64}", snapshot_id) is None:
            raise ValueError("Invalid storage snapshot ID")
        self._snapshot_id = snapshot_id
        self._fixture_diffs = frozenset(approved_fixture_diffs)
        if self._policy.runtime == "docker_admitted":
            if self._fixture_diffs:
                raise ValueError("Docker execution uses independent admission")
            self._admission = validate_admission(self._task, admission).snapshot()
        else:
            if admission is not None or not self._fixture_diffs or any(
                not isinstance(value, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
                for value in self._fixture_diffs
            ):
                raise ValueError("Native execution requires approved exact fixture diff hashes")
            require_trusted_fixture(self._task)
            self._admission = None
        self._contract_payload = None
        self._contract_ids = ()
        if semantic_contract is not None:
            contract = SemanticContract.model_validate(semantic_contract.model_dump())
            if self._admission is not None:
                raise ValueError("Semantic contract plugin requires a qualified native fixture runtime")
            if any(example.module.replace(".", "/") + ".py" not in task.allowed_source_paths
                   for example in contract.examples):
                raise ValueError("Contract module must belong to the admitted editable fixture paths")
            payload = canonical_bytes(contract.model_dump(mode="json"))
            if len(payload) > 8192:
                raise ValueError("Semantic contract exceeds the native command byte limit")
            self._contract_payload = payload.decode("utf-8")
            self._contract_ids = tuple(example.node_id for example in contract.examples)
        self._profile_hash = digest(canonical_bytes({
            "task": self._task.model_dump(mode="json"), "policy": self._policy.model_dump(mode="json"),
            "admission": self._admission["admission_hash"] if self._admission else None,
            "fixture_diff_hashes": sorted(self._fixture_diffs),
            "semantic_contract": self._contract_payload,
        }))

    async def run_diff_tests(self, request: c.DiffRequest, context) -> c.TestEvidence:
        request = c.DiffRequest.model_validate(request.model_dump())
        stop, done = threading.Event(), threading.Event()
        gate = threading.Lock()
        started = False

        def work():
            nonlocal started
            with gate:
                if stop.is_set():
                    return None
                started = True
            try:
                return self._run(request, context, stop)
            finally:
                done.set()

        try:
            return await anyio.to_thread.run_sync(work, abandon_on_cancel=True)
        except anyio.get_cancelled_exc_class():
            with gate:
                stop.set()
                active = started
            try:
                cancel_request(context)
            finally:
                if active:
                    with anyio.CancelScope(shield=True):
                        await anyio.to_thread.run_sync(done.wait)
            raise

    def _run(self, request, context, stop):
        task, policy = self._task, self._policy
        check_source(context)
        if (c.SnapshotBinding.from_context(context) != self._binding
                or no_links(task.source_repo).resolve(strict=True) != context.repo_root):
            raise ValueError("Diff tests task, source or snapshot binding mismatch")
        if self._admission is None:
            require_trusted_fixture(task)
            if request.diff_hash not in self._fixture_diffs:
                raise ValueError("Diff bytes are not approved for native fixture execution")
        end = time.monotonic() + min(context.limits.worker_seconds, context.deadline - time.time())

        def guard():
            check_context(context)
            if stop.is_set() or time.monotonic() >= end:
                raise TimeoutError("Diff test request stopped or expired")

        state = {"status": "NOT_RUN", "coverage": "PARTIAL", "reasons": (), "applied_count": 0,
                 "executed": False, "baseline": None, "candidate": None}
        workspace = resolve_read_path(context.lease_root, self.candidate_workspace)
        patch_policy = PatchPolicy(task.allowed_source_paths, task.protected_paths, policy.max_diff_bytes,
                                   policy.max_files, policy.max_changed_lines)
        try:
            patch = parse_unified_diff(request.diff, patch_policy)
        except (ValueError, SyntaxError, TypeError, AttributeError):
            state["reasons"] = ("PATCH_POLICY_REJECTED",)
        else:
            guard()
            workspace.mkdir(exist_ok=False)
            try:
                try:
                    self._measure(workspace, patch, state, end, stop, guard, context.limits.output_bytes)
                except (OSError, RuntimeError, ValueError) as error:
                    state.update(status="ERROR", coverage="PARTIAL", reasons=("DIFF_TEST_EXECUTION_ERROR",),
                                 error_type=type(error).__name__)
            finally:
                if no_links(workspace).resolve() != workspace or workspace.parent != context.lease_root:
                    raise ValueError("Refusing cleanup outside the owned candidate workspace")
                shutil.rmtree(workspace)
        guard()
        receipt = c.TestReceipt(workspace=self.candidate_workspace, diff_hash=request.diff_hash, admitted=True,
                                applied_count=state["applied_count"], executed=state["executed"], cleaned=not workspace.exists())
        return self._publish(context, request, receipt, state, guard)

    def _measure(self, workspace, patch, state, end, stop, guard, output_cap):
        task, policy = self._task, self._policy
        if self._admission is None:
            lease = create_workspace(task.source_repo, workspace, deadline=end)
            executor = DeadlineExecutor(lease, end, output_cap, cancel_event=stop)
        else:
            lease = prepare_admitted_workspace(task, self._admission, workspace, deadline=end)
            executor = None
        with lease:
            if executor is None:
                executor = DockerExecutor(lease, task, self._admission, end, output_cap, cancel_event=stop)
            if self._contract_payload is not None:
                executor = ContractExecutor(executor, self._contract_payload)
            guard()
            before = inventory_hash(inventory(lease.path))
            baseline = run_tests(lease, task.fallback_scope, executor, policy.command_timeout)
            guard()
            state["baseline"] = _test_summary(baseline)
            if inventory_hash(inventory(lease.path)) != before:
                raise ValueError("Baseline tests altered the private source")
            observed = {baseline["outcomes"].get(node_id) for node_id in self._contract_ids}
            if observed - {"PASS"}:
                measured_failure = baseline["status"] != "ERROR" and observed <= {"PASS", "FAIL"}
                state.update(status="NOT_RUN" if measured_failure else "ERROR",
                             reasons=("BASELINE_CONTRACT_NOT_QUALIFIED",))
                return
            required = _qualified_failures(task.failing_selectors, baseline)
            if not required:
                state.update(status="ERROR" if baseline["status"] == "ERROR" else "NOT_RUN",
                             reasons=("BASELINE_TESTS_INCOMPLETE" if baseline["status"] == "ERROR"
                                      else "BASELINE_NOT_QUALIFIED",))
                return
            state.update(required_failures=required, baseline_inventory_hash=before)
            guard()
            applied = apply_patch(lease, patch, executor)
            state["applied_count"] = int(len(lease.patch_evidence) >= 2 and lease.patch_evidence[1]["status"] == "PASS")
            guard()
            if applied.status != "PASS":
                state.update(status="ERROR" if applied.status == "ERROR" else "NOT_RUN",
                             reasons=("PATCH_APPLY_FAILED",))
                return
            state.update(changed_paths=applied.changed_files, candidate_inventory_hash=lease.applied_inventory_hash,
                         executed=True)
            candidate = run_tests(lease, task.fallback_scope, executor, policy.command_timeout)
            guard()
            state["candidate"] = _test_summary(candidate)
            after = inventory(lease.path)
            if inventory_hash(after) != lease.applied_inventory_hash:
                raise ValueError("Candidate tests altered the private source")
            state["changed_source_hashes"] = {path: after[path] for path in applied.changed_files}
            lease.assert_original()
            status, reasons = assess_transition({"required_ids": required, "tests": baseline}, candidate)
            state.update(status=status, coverage="COMPLETE" if status in {"PASS", "FAIL"} else "PARTIAL",
                         reasons=tuple(dict.fromkeys(reasons)))

    def _publish(self, context, request, receipt, state, guard):
        binding = c.SnapshotBinding.from_context(context)
        record = {"profile": PROFILE, "profile_hash": self._profile_hash, "binding": binding.model_dump(),
                  "snapshot_id": self._snapshot_id,
                  "diff_hash": request.diff_hash, "scope": self._task.fallback_scope, "receipt": receipt.model_dump(),
                  "runtime": self._policy.runtime, "coverage_count": "NOT_MEASURED", **state}
        if self._contract_payload is not None:
            record["semantic_contract"] = {"definition": self._contract_payload, "sha256": digest(self._contract_payload)}
        raw = encode_json(record)
        if len(raw) > context.limits.read_bytes:
            record.update(status="ERROR", coverage="PARTIAL", reasons=("EVIDENCE_BYTE_LIMIT",),
                          baseline=None, candidate=None, required_failures=())
            raw = encode_json(record)
        if len(raw) > context.limits.read_bytes:
            raise ValueError("Diff test evidence exceeds host byte limit")
        name = f"tv3-ev3-{uuid4().hex}.json"
        with request_commit_guard(context):
            check_source(context)
            target = resolve_read_path(context.output_root, name)
            guard()
            atomic_json(target, record)
        return c.TestEvidence(binding=binding, diff_hash=request.diff_hash, status=record["status"],
                              coverage=record["coverage"], scope=self._task.fallback_scope, reasons=record["reasons"],
                              receipt=receipt, evidence=(c.EvidenceRef(path=name, sha256=digest(raw)),))


def _qualified_failures(selectors, baseline):
    if baseline["status"] != "FAIL" or "ERROR" in baseline["outcomes"].values():
        return ()
    try:
        required = expand_required(selectors, baseline["node_ids"])
    except ValueError:
        return ()
    outcomes = baseline["outcomes"]
    failures = {key for key, status in outcomes.items() if status == "FAIL"}
    if not failures <= set(required) or any(outcomes.get(key) not in {"PASS", "FAIL"} for key in required):
        return ()
    return tuple(sorted(failures))


def _test_summary(result):
    command = result["command"]
    junit = result.get("junit_xml")
    return {"status": result["status"], "reason": result["reason"], "outcomes": result["outcomes"],
            "junit_sha256": digest(junit) if junit is not None else None, "exit_code": command["exit_code"],
            "complete": command["complete"], "duration_ms": command["duration_ms"],
            "docker_cleanup": command.get("docker_cleanup", {}).get("status")}
