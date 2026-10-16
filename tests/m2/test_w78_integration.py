"""Exercise the relocated launcher, not the independent source directory."""
import json
import hashlib
from pathlib import Path
import subprocess
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[2]
EMBEDDED = ROOT / "M2_week_7_8"
CORE_PYTHON = EMBEDDED / ".venv/Scripts/python.exe"


def invoke(*args, python=CORE_PYTHON):
    launcher = ROOT / "run_m2_abc.ps1"
    if not launcher.is_file():
        pytest.fail("VGAR M2 integration launcher is not implemented")
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(launcher),
         "-Python", str(python), *args],
        cwd=ROOT.parent, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )


def test_readsaved_uses_embedded_runtime_and_current_vgar():
    output = EMBEDDED / "results/integration-tests" / uuid.uuid4().hex
    result = invoke("-Mode", "ReadSaved", "-OutputRoot", str(output))
    assert result.returncode == 0, result.stdout + result.stderr
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    assert summary["mode"] == "ReadSaved" and summary["status"] == "PASS"
    assert len(summary["cases"]) == 3
    assert all(case["status"] == "PASS" and not case["gate_errors"] for case in summary["cases"])
    preflight = json.loads((summary_path.parent / "preflight.json").read_text(encoding="utf-8"))
    assert Path(preflight["reference"]["root"]).resolve() == ROOT
    assert preflight["runtime_revision"] == "r002-vgar-i001"
    assert not list(summary_path.parent.rglob("raw_model_output.txt")), "ReadSaved must not generate"


def test_output_outside_embedded_results_is_rejected(tmp_path):
    output = tmp_path / "must-not-exist"
    result = invoke("-Mode", "ReadSaved", "-OutputRoot", str(output))
    assert result.returncode != 0
    assert not output.exists()


def test_relative_interpreter_saved_root_and_output_are_bound_before_chdir():
    base = ROOT.name + "/M2_week_7_8"
    relative_output = base + "/results/integration-tests/" + uuid.uuid4().hex
    result = invoke(
        "-Mode", "ReadSaved", "-OutputRoot", relative_output,
        "-SavedRoot", base + "/results/final_acceptance/2026-10-15-v11-r002",
        python=base + "/.venv/Scripts/python.exe",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((ROOT.parent / relative_output / "summary.json").read_text(encoding="utf-8-sig"))
    assert summary["status"] == "PASS" and len(summary["cases"]) == 3
    assert all(case["historical_reaudit"] for case in summary["cases"])


def test_source_and_all_non_relocated_content_preserved():
    receipt_path = EMBEDDED / "integration/relocation.json"
    if not receipt_path.is_file():
        pytest.fail("Lossless-copy receipt is not implemented")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["integration_id"] == "r002-vgar-i001"
    assert receipt["copied_files"] > 13000
    assert receipt["copy_mismatches"] == []
    assert set(receipt["relocated_files"]) == {
        "config/source_pin.json", "config/demo.json", "pyproject.toml",
        "tests/conftest.py", "test_abc_v11_r002.ps1",
        "src/vgar_m2_w78/b_inputs.py",
    }
    before = json.loads((ROOT / "docs/audit/2026-10-16-m2-w7-w8-integration/before.json").read_text(encoding="utf-8"))
    for relative, metadata in before["source_files"].items():
        if relative.startswith(("src/", "scripts/", "prompts/", "examples/", "tests/", "docs/")) and "__pycache__" not in relative:
            file = (EMBEDDED / "integration/originals" / relative
                    if relative in receipt["relocated_files"] else EMBEDDED / relative)
            assert file.is_file(), relative
            assert hashlib.sha256(file.read_bytes()).hexdigest() == metadata["sha256"], relative


def test_config_drift_is_rejected_before_audit():
    # Change only a temporary copied config and point the copied runner at it.
    # A complete isolated clone is unnecessary: its first hash gate must fail.
    import tempfile
    import shutil
    with tempfile.TemporaryDirectory(dir=ROOT / "results", prefix="m2-drift-") as directory:
        copied = Path(directory)
        for folder in ("src", "config"):
            shutil.copytree(EMBEDDED / folder, copied / folder,
                            ignore=shutil.ignore_patterns("__pycache__"))
        campaign = "results/b_repair/2026-10-15-evidence-driven-b"
        (copied / campaign / "revisions").mkdir(parents=True)
        for file in ("frozen_inputs.json", "revisions/r002.json"):
            shutil.copy2(EMBEDDED / campaign / file, copied / campaign / file)
        # Bind reference to VGAR at this new depth without altering the hash expected by runner.
        pin = copied / "config/source_pin.json"
        value = json.loads(pin.read_text(encoding="utf-8"))
        value["reference_root"] = str(ROOT)
        pin.write_text(json.dumps(value), encoding="utf-8")
        script = copied / "test_abc_v11_r002.ps1"
        shutil.copy2(EMBEDDED / script.name, script)
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
             "-Mode", "ReadSaved", "-Python", str(CORE_PYTHON)],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        assert result.returncode != 0
        assert "Qualified" in result.stdout + result.stderr
