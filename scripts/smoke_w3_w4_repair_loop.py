"""W3-W4 end-to-end smoke: LLM planning -> MCP -> patch -> test -> evidence -> repair.

This script intentionally uses a tiny disposable fixture so the smoke test is
safe to run against the real repository without modifying it.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from vgar.agents.core import create_core_agent
from vgar.contracts.evidence import EvidenceBundle, VerificationResult
from vgar.repair.evidence_writer import begin_run, finish_run
from vgar.repair.test_runner import run_tests
from vgar.repair.workspace import create_workspace, fingerprint_source

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / ".vgar_smoke_fixture"


def prepare_fixture() -> Path:
    if FIXTURE.exists():
        import shutil
        shutil.rmtree(FIXTURE)
    (FIXTURE / "tests").mkdir(parents=True)
    (FIXTURE / "calculator.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a - b\n",
        encoding="utf-8",
    )
    (FIXTURE / "tests" / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    return FIXTURE


async def main() -> None:
    source = prepare_fixture()
    with tempfile.TemporaryDirectory(prefix="vgar-w3w4-" ) as temp:
        temp_root = Path(temp)
        with create_workspace(source, temp_root) as lease:
            run_dir = ROOT / "artifacts" / "w3_w4_repair"
            handle = begin_run(
                run_dir,
                task_id="w3-w4-repair-001",
                source_repo=source,
                source_hash_before=lease.source_hash_before,
                worktree_id=lease.worktree_id,
                argv=["python", "-m", "pytest", "tests/test_calculator.py::test_add"],
                cwd=lease.path,
                timeout_seconds=30,
            )

            # 1) Baseline: the fixture must fail before repair.
            baseline = run_tests(lease.path, ("tests/test_calculator.py::test_add",), 30)
            assert baseline.status == "FAIL", baseline.model_dump()

            # 2) Real LangChain agent gets the task and the real MCP tools.
            agent = await create_core_agent()
            prompt = f"""
You are executing W3-W4 repair smoke test in {lease.path}.
Task: fix tests/test_calculator.py::test_add.
Required flow: inspect with MCP repository tools, reason about the smallest edit,
apply the edit with repository.apply_patch, then run execution.run_pytest.
If verification fails, inspect the failure and repair once more. Do not use shell.
The correct implementation of add(a,b) must return a+b.
"""
            result = None
            final_test = baseline
            repair_attempts = 0

            # 3) Bounded repair loop. Every iteration is followed by an independent
            # verification gate; the LLM is never allowed to declare success itself.
            for repair_attempts in range(1, 4):
                iteration_prompt = prompt
                if final_test.status != "FAIL":
                    iteration_prompt += "\nPrevious verification:\n" + final_test.stdout + "\n" + final_test.stderr
                result = await agent.ainvoke({
                    "messages": [
                        SystemMessage(content="You are a software repair agent. Never claim success without test evidence."),
                        HumanMessage(content=iteration_prompt),
                    ]
                })
                final_test = run_tests(lease.path, ("tests/test_calculator.py::test_add",), 30)
                if final_test.status == "PASS":
                    break

            # 4) Independent verification gate. The agent's claim is not trusted.
            evidence = VerificationResult(
                patch_applied=lease.path.joinpath("calculator.py").read_text(encoding="utf-8")
                != source.joinpath("calculator.py").read_text(encoding="utf-8"),
                tests=final_test,
            )
            bundle = EvidenceBundle(
                run_id=handle.run_id,
                task_id="w3-w4-repair-001",
                source_repo=str(source),
                source_hash_before=lease.source_hash_before,
                source_hash_after=fingerprint_source(lease.path),
                worktree_id=lease.worktree_id,
                verification=evidence,
                metadata={
                    "stage": "W3-W4",
                    "repair_attempts": repair_attempts,
                    "flow": ["LLM planning", "MCP inspection", "MCP patch", "MCP verification", "evidence"],
                    "agent_result": str(result)[-8000:],
                },
            )
            evidence_path = finish_run(
                handle,
                final_test,
                source_hash_after=bundle.source_hash_after,
                bundle=bundle,
            )

            assert final_test.status == "PASS", final_test.model_dump()
            print(json.dumps({
                "status": "PASS",
                "baseline": baseline.status,
                "final": final_test.status,
                "evidence": str(evidence_path),
                "repair_attempts": repair_attempts,
                "worktree_id": lease.worktree_id,
            }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
