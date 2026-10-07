"""Record the existing comparator CLI; do not re-run or merge retrieval tasks."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from vgar.evaluation.retrieval.evidence import record_command

baseline = ROOT / "artifacts/fixes/w3-w6/manual10-no-jedi/baseline-recovery/20261007T020222087444Z-9d7a6463840c/recovered-run"
graph = ROOT / "results/retrieval/20261007T114731162059Z-f27e07ec6a8b"
path, evidence = record_command(
    [sys.executable, "-B", str(ROOT / "scripts/compare_graph_vs_bm25.py"),
     str(ROOT), str(baseline), str(graph)],
    ROOT, Path(__file__).parent / "paired23-comparison-execution", timeout=120,
    kind="reopened-paired-comparison-command",
)
print(json.dumps({"evidence": str(path), "exit_code": evidence["exit_code"],
                  "stdout": evidence["stdout"], "stderr": evidence["stderr"]}, ensure_ascii=False))
raise SystemExit(evidence["exit_code"])
