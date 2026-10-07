"""Retain final scoped whitespace check; no staging, commit, or push."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from vgar.evaluation.retrieval.evidence import record_command

path, result = record_command(
    ["git", "diff", "--check", "--", "src", "tests", "scripts", "docs", "README.md", "PROGRESS.md",
     "artifacts/fixes/w3-w6/review_doc_checks.py", "artifacts/fixes/w3-w6/verify_explanation_document.py"],
    ROOT, Path(__file__).parent / "final-diff-check", timeout=30, kind="reopened-scoped-diff-check",
)
print(json.dumps({"evidence": str(path), "status": result["status"], "exit_code": result["exit_code"],
                  "stdout": result["stdout"], "stderr": result["stderr"]}, ensure_ascii=False))
raise SystemExit(result["exit_code"])
