"""Capture pre-patch pytest evidence without modifying the input repository."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from vgar.contracts.evidence import EvidenceBundle, TestRunResult, VerificationResult
from vgar.contracts.repair import FailureReason

from .evidence_writer import begin_run, finish_run
from .test_runner import run_tests
from .workspace import create_workspace, fingerprint_source


def run_baseline(source_repo: Path, selectors: tuple[str, ...], artifact_dir: Path, task_id: str,
                 *, temp_root: Path | None = None, timeout_seconds: float = 120) -> EvidenceBundle:
    source = Path(source_repo).resolve(strict=True)
    temporary = Path(temp_root or os.getenv("VGAR_M2_TEMP_ROOT", str(source.parent / "m2-temp"))).resolve()
    with create_workspace(source, temporary) as lease:
        handle = begin_run(artifact_dir, task_id=task_id, source_repo=source,
                           source_hash_before=lease.source_hash_before, worktree_id=lease.worktree_id,
                           argv=[sys.executable, "-m", "pytest", *selectors], cwd=lease.path,
                           timeout_seconds=timeout_seconds)
        try:
            result = run_tests(lease.path, selectors, timeout_seconds)
        except Exception as exc:
            result = TestRunResult(status="ERROR", command="pytest invocation failed",
                                   argv=[sys.executable, "-m", "pytest", *selectors], exit_code=None,
                                   duration_ms=0, stdout="", stderr=str(exc), timeout_seconds=timeout_seconds,
                                   reason=FailureReason(code="INTERNAL_ERROR", message=str(exc)))
        after = fingerprint_source(source)
        reasons = [] if after == lease.source_hash_before else [
            FailureReason(code="WORKTREE_ERROR", message="Input source changed during baseline")]
        bundle = EvidenceBundle(run_id=handle.run_id, task_id=task_id, source_repo=str(source),
                                source_hash_before=lease.source_hash_before, source_hash_after=after,
                                worktree_id=lease.worktree_id, artifact_path=str(handle.path),
                                verification=VerificationResult(patch_applied=False, tests=result, reasons=reasons),
                                metadata={"mode": "pre_patch_baseline", "selectors": list(selectors)})
        finish_run(handle, result, source_hash_after=after, bundle=bundle)
        return bundle
