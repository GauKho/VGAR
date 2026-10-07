"""Real stdio transport and scripted LangGraph agent, never real model inference."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from vgar.evaluation.retrieval.evidence import new_run, write_json, utc_now
from vgar.repair.workspace import fingerprint_source

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script, args, marker", [
    ("smoke_w3_w4_full.py", ["--strict-resources"], "W3-W4 FULL SMOKE PASS"),
    ("smoke_w3_w4_agent.py", ["--model", "scripted"], "W3-W4 AGENT SMOKE PASS"),
])
def test_real_stdio_smoke_saves_transcript_audit_patch_and_m2_evidence(script, args, marker):
    directory, record = new_run(ROOT / "artifacts/fixes/w3-w6", "milestone-4-stdio")
    source = ROOT / "tests/fixtures/m2/failing_repo"
    before = fingerprint_source(source)
    argv = [sys.executable, "-B", str(ROOT / "scripts" / script), *args, "--keep"]
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    try:
        completed = subprocess.run(argv, cwd=ROOT, env=environment, capture_output=True,
                                   encoding="utf-8", errors="replace", timeout=120)
        record.update(argv=argv, cwd=str(ROOT), timeout_seconds=120, stdout=completed.stdout,
                      stderr=completed.stderr, exit_code=completed.returncode,
                      status="PASS" if completed.returncode == 0 else "ERROR", complete=True)
    except subprocess.TimeoutExpired as error:
        record.update(argv=argv, cwd=str(ROOT), timeout_seconds=120, stdout=str(error.stdout or ""),
                      stderr=str(error.stderr or ""), exit_code=None, status="ERROR", complete=False)
    record.update(ended_utc=utc_now(), duration_seconds=time.monotonic() - started,
                  source_hash_before=before, source_hash_after=fingerprint_source(source), inference="NOT_RUN")
    # Copy only this smoke's generated temp artifacts, never original source/cache.
    matches = re.findall(r"^artifacts: (.+)$", record["stdout"], flags=re.MULTILINE)
    if matches:
        work = Path(matches[-1].strip())
        shutil.copytree(work, directory / "transport")
        record["transport_artifacts"] = "transport"
    write_json(directory / "result.json", record)
    assert record["exit_code"] == 0, f"{directory}: {record['stdout']}\n{record['stderr']}"
    assert marker in record["stdout"]
    assert before == record["source_hash_after"]
    assert matches, "smoke must retain portable artifact copies"
    events = [json.loads(line) for line in (directory / "transport/mcp_audit.jsonl").read_text(encoding="utf-8").splitlines()]
    tools = {event["payload"].get("tool") for event in events}
    assert {"apply_patch", "run_pytest"} <= tools
    assert list((directory / "transport/m2-tool-runs").glob("*.json"))
    assert "+    return 42" in (directory / "transport/patch.diff").read_text(encoding="utf-8")
