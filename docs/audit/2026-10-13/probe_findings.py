"""Bounded diagnostic reproductions on disposable inputs, not a repair run.

Does not change source/tests of VGAR or load any model. Expected findings are
reported as observations, never mislabeled as a successful product test.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.mcp.servers import repository_server
from vgar.repair.test_runner import run_tests


def main() -> None:
    findings = {}
    temp_root = ROOT.parent / ".audit-tmp" / "vgar-probes-20261013"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="probe-", dir=temp_root) as directory:
        work = Path(directory)
        fixture = OUTPUT / "probe_inputs"
        repo = work / "graph-repo"
        (repo / "src").mkdir(parents=True)
        for name in ("a.py", "b.py"):
            shutil.copy2(fixture / name, repo / "src" / name)
        document = PythonGraphBuilder(repo_key="audit/external-binding", repository_revision="fixture").build(repo)
        nodes = {node["id"]: node for node in document["nodes"]}
        calls = [edge for edge in document["edges"] if edge["type"] == "CALLS"]
        findings["external_import_unique_name_fallback"] = {
            "observation": "unresolved explicit external import receives an internal CALLS target",
            "call_targets": [{"path": nodes[edge["target_id"]]["path"],
                              "qualified_name": nodes[edge["target_id"]]["qualified_name"],
                              "confidence": edge["confidence"],
                              "binding_kind": edge["properties"].get("binding_kind")}
                             for edge in calls],
        }
        store = SQLiteGraphStore(work / "graph.db")
        store.ingest(document)
        service = SQLiteGraphService(store)
        target_id = calls[0]["target_id"]
        raw = service.get_node(target_id)
        try:
            service.get_node(quote(target_id, safe=""))
        except Exception as exc:
            findings["encoded_resource_id"] = {"raw_id_resolves": raw.repo.node_id == target_id,
                                                 "encoded_id_error": type(exc).__name__, "message": str(exc)}
        try:
            service.get_related_context([], 8000, graph_version=document["graph_version"], task_id="audit")
        except Exception as exc:
            findings["unconfigured_context_service"] = {"error": type(exc).__name__, "message": str(exc)}

        intended = work / "intended-workspace"
        alternate = work / "alternate-unrelated-dummy"
        intended.mkdir()
        alternate.mkdir()
        shutil.copy2(fixture / "demo.py", intended / "demo.py")
        shutil.copy2(fixture / "demo.py", alternate / "demo.py")
        response = repository_server.apply_patch(str(alternate), "demo.py", "return 0", "return 42")
        findings["agent_supplied_repository_root"] = {
            "alternate_dummy_patch_status": response["status"],
            "intended_workspace_untouched": (intended / "demo.py").read_bytes() == (fixture / "demo.py").read_bytes(),
            "alternate_dummy_was_modified": (alternate / "demo.py").read_bytes() != (fixture / "demo.py").read_bytes(),
            "scope": "only throwaway audit folders; no original repository edited",
        }

        skip_repo = work / "skip-only-repo"
        (skip_repo / "tests").mkdir(parents=True)
        shutil.copy2(fixture / "skip_case.py", skip_repo / "tests" / "test_required.py")
        result = run_tests(skip_repo, ("tests/test_required.py",), 20)
        findings["skip_only_pytest_is_reported_pass"] = {
            "status": result.status, "exit_code": result.exit_code, "counts": result.case_counts,
            "stdout": result.stdout, "stderr": result.stderr,
            "case_statuses": [case.status for case in result.cases],
        }
    destination = OUTPUT / "probe-findings.json"
    destination.write_text(json.dumps(findings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"findings": list(findings), "output": str(destination)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
