import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from m2_retrieval.m1_adapter import compare_run
from m2_retrieval.report import write_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--exports", type=Path, default=ROOT / "data" / "m1_exports")
    args = parser.parse_args()
    directory, result = compare_run(args.run, args.exports, ROOT / "results" / "comparison")
    print(f"Status={result['status']}; pairs={result['paired_tasks']}/{result['eligible_bm25_tasks']}")
    print(f"Evidence: {directory / 'result.json'}\nReport: {write_report(args.run, directory)}")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
