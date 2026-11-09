"""Controller errors must be read-only and fail closed before launching children."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def controller():
    path = ROOT / "scripts/mcp_server/check_runtime.py"
    spec = importlib.util.spec_from_file_location("runtime_controller", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_output_refused_without_change(tmp_path):
    module = controller()
    out = tmp_path / "old"
    out.mkdir()
    marker = out / "keep.json"
    marker.write_text('{"keep":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        module.main(["--client-python", sys.executable, "--server-python", sys.executable,
                     "--output-root", str(out)])
    assert json.loads(marker.read_text()) == {"keep": True}
    assert list(out.iterdir()) == [marker]


def test_missing_interpreter_does_not_create_output(tmp_path):
    module = controller()
    out = tmp_path / "new"
    with pytest.raises(ValueError, match="interpreter"):
        module.main(["--client-python", str(tmp_path / "absent.exe"), "--server-python", sys.executable,
                     "--output-root", str(out)])
    assert not out.exists()


def test_probe_failure_cannot_be_accepted(tmp_path, monkeypatch):
    module = controller()
    calls = []

    def failed(argv, cwd, timeout_seconds, **kwargs):
        calls.append(argv)
        return {"status": "FAIL", "complete": True, "exit_code": 1, "stdout": "", "stderr": "probe failed"}

    monkeypatch.setattr(module, "run_bounded", failed)
    out = tmp_path / "new"
    code = module.main(["--client-python", sys.executable, "--server-python", sys.executable,
                        "--require-no-langchain", "--output-root", str(out)])
    assert code == 1
    assert len(calls) == 1
    summary = json.loads((out / "summary.json").read_text())
    assert summary["status"] == "FAIL"
    assert summary["wire"] == []


def test_optimized_worker_still_rejects_inconsistent_wire_payload(tmp_path):
    code = '''
import importlib.util,json
from types import SimpleNamespace
spec=importlib.util.spec_from_file_location('worker',WORKER)
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
value={'status':'PASS','data':{'x':1},'error':None,'metadata':{'request_id':'r','duration_ms':0}}
other={**value,'data':{'x':2}}
worker.payload(SimpleNamespace(is_error=False,structured_content=value,content=[SimpleNamespace(type='text',text=json.dumps(other))]))
'''.replace("WORKER", repr(str(ROOT/"scripts/mcp_server/_runtime_worker.py")))
    result = subprocess.run([sys.executable, "-O", "-B", "-c", code], cwd=tmp_path,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True,
                            text=True, encoding="utf-8", timeout=20, check=False)
    assert result.returncode != 0, "Optimized worker accepted contradictory structured/text data"
    assert "Structured/text payload mismatch" in result.stderr


@pytest.mark.parametrize("prompt_gate", [None, "FAIL"])
def test_controller_does_not_accept_listing_only_prompt_gate(tmp_path, monkeypatch, prompt_gate):
    module = controller()
    def fake(argv, cwd, timeout_seconds, **kwargs):
        if any("_runtime_probe.py" in value for value in argv):
            return {"exit_code": 0, "complete": True, "stdout": '{"status":"PASS"}'}
        if "-c" in argv:
            return {"exit_code": 0, "complete": True, "stdout": "2.2.0"}
        server = argv[argv.index("--server") + 1]
        receipt = {"status": "PASS", "protocol": "synthetic", "prompt_gate": "NOT_APPLICABLE"}
        if server == "graph": receipt["prompt_gate"] = prompt_gate
        (Path(cwd) / "wire.json").write_text(json.dumps(receipt), encoding="utf-8")
        return {"exit_code": 0, "complete": True, "stdout": ""}
    monkeypatch.setattr(module, "run_bounded", fake)
    out = tmp_path / "new"
    result = module.main(["--client-python", sys.executable, "--server-python", sys.executable, "--output-root", str(out)])
    assert result == 1
    assert json.loads((out / "summary.json").read_text())["prompt_gate"] == "FAIL"
