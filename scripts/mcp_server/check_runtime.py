"""Bounded, scripted MCP runtime gate. No model, agent loop, Docker or campaign."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))

from vgar.repair.executor import run_bounded


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-python", required=True)
    parser.add_argument("--server-python", required=True)
    parser.add_argument("--require-no-langchain", action="store_true")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    out = Path(args.output_root).resolve()
    if out.exists():
        raise ValueError("Runtime output already exists; choose a new output directory")
    for value in (args.client_python, args.server_python):
        if not Path(value).is_file():
            raise ValueError(f"Missing interpreter: {value}")
    out.mkdir(parents=True, exist_ok=False)
    environment = {"PYTHONPATH": str(ROOT/"src"), "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONOPTIMIZE": "0", "VGAR_GRAPH_BACKEND": "demo", "VGAR_MCP_AUDIT_LOG": str(out/"probe-audit.jsonl")}
    probe = [args.server_python, "-B", str(Path(__file__).with_name("_runtime_probe.py"))]
    if args.require_no_langchain:
        probe.append("--require-no-langchain")
    record = run_bounded(tuple(probe), out, 30, output_cap=1024*1024, environment=environment)
    dump(out/"probe-command.json", record)
    summary = {"status": "FAIL", "wire": [], "prompt_gate": "NOT_RUN", "scope": "legacy runtime, resources and prompt; synthetic trusted repair fixture, no generator/model"}
    if record["exit_code"] != 0 or not record["complete"]:
        dump(out/"summary.json", summary)
        return 1
    inventory = json.loads(record["stdout"])
    if inventory["status"] != "PASS":
        dump(out/"summary.json", summary)
        return 1
    dump(out/"runtime-inventory.json", inventory)
    # Controller and client normally share the same interpreter. A legacy SDK1
    # client is launched from that interpreter's separate invocation of this CLI.
    client_probe = run_bounded((args.client_python, "-B", "-c", "from importlib.metadata import version; print(version('mcp'))"), out, 20, environment=environment)
    dump(out/"client-version-command.json", client_probe)
    if client_probe["exit_code"] != 0 or not client_probe["complete"]:
        dump(out/"summary.json", summary)
        return 1
    major = int(client_probe["stdout"].strip().split(".")[0])
    if major not in (1, 2):
        dump(out/"summary.json", summary)
        return 1
    modes = ("2026-07-28", "legacy") if major == 2 else ("legacy",)
    for mode in modes:
        for server in ("graph", "repository", "execution", "repair"):
            target = out/(mode+"-"+server)
            target.mkdir()
            shutil.copy2(ROOT/"artifacts/sample_graph.db", target/"sample_graph.db")
            lease = target/"lease"
            (lease/"tests").mkdir(parents=True)
            (lease/"auth.py").write_text("def login(name):\n    return bool(name)\n", encoding="utf-8")
            (lease/"tests/test_auth.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
            command = (args.client_python, "-B", str(Path(__file__).with_name("_runtime_worker.py")), "--server", server, "--mode", mode, "--server-python", args.server_python, "--output", str(target))
            result = run_bounded(command, target, 240, output_cap=2*1024*1024, environment=environment)
            dump(target/"command.json", result)
            wire_path = target/"wire.json"
            wire = json.loads(wire_path.read_text(encoding="utf-8")) if wire_path.is_file() else {"status": "FAIL", "error": "No worker receipt"}
            passed = result["exit_code"] == 0 and result["complete"] and wire["status"] == "PASS" and (server != "graph" or wire.get("prompt_gate") == "PASS")
            summary["wire"].append({"server": server, "requested_mode": mode, "protocol": wire.get("protocol"), "status": "PASS" if passed else "FAIL", "receipt": str(wire_path.relative_to(out)), "prompt_gate": wire.get("prompt_gate", "NOT_RUN")})
    graph_gates = [row for row in summary["wire"] if row["server"] == "graph"]
    summary["prompt_gate"] = "PASS" if graph_gates and all(row["prompt_gate"] == "PASS" for row in graph_gates) else "FAIL"
    summary["status"] = "PASS" if summary["wire"] and all(x["status"] == "PASS" for x in summary["wire"]) and summary["prompt_gate"] == "PASS" else "FAIL"
    dump(out/"summary.json", summary)
    print(json.dumps(summary))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
