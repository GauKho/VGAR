import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from m2_retrieval.evaluation import evaluate_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--budget-tokens", type=int, default=4000)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1 or args.budget_tokens < 1:
        parser.error("limit/budget must be positive")
    directory, record = evaluate_manifest(ROOT, args.manifest, args.limit, args.budget_tokens, args.offline, args.resume)
    print(f"\nEvidence: {directory / 'result.json'}\nCompleted={record['summary']['completed_tasks']}; failed={record['summary']['failed_tasks']}")
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
