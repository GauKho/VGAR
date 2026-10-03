"""Run stdlib tests and record command, output, duration and source hashes."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ["PYTHONPATH"] = str(ROOT / "src")
from m2_retrieval.evidence import record_command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", default="test*.py")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    args = parser.parse_args()
    path, record = record_command([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", args.pattern, "-v"], ROOT, ROOT / "results" / "tests", args.timeout_seconds)
    print(record["stdout"], end="")
    print(record["stderr"], end="", file=sys.stderr)
    print(f"\nEvidence: {path}\nStatus: {record['status']}; exit={record['exit_code']}")
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
